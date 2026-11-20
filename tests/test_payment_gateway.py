"""Public API-contract and transport checks; no real gateway calls or test cards."""

import json
import urllib.error
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core.payments.gateway import BASE, Gateway, NoRedirect, ProviderFailure, exact_json


@override_settings(
    PAYMENT_SANDBOX_ENABLED=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox-source",
    BANQUEST_API_PIN="fake-pin",
)
class GatewayContractTests(SimpleTestCase):
    def test_exact_json_preserves_decimal_numbers_without_converting_to_strings(self):
        wire = exact_json({"amount": Decimal("16.47"), "capture": True, "name": '"quoted"'})
        self.assertIn('"amount":16.47', wire)
        self.assertEqual(json.loads(wire, parse_float=Decimal)["amount"], Decimal("16.47"))
        with self.assertRaises(ValidationError):
            exact_json({"amount": 16.47})

    def test_transport_is_pinned_to_tls_sandbox_and_has_no_redirect_fallback(self):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"amount":16.47}'
        context = MagicMock()
        context.__enter__.return_value = response
        with patch("urllib.request.build_opener") as make:
            make.return_value.open.return_value = context
            result = Gateway().request("POST", "transactions/charge", {"amount": Decimal("16.47")})
            request = make.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, BASE + "transactions/charge")
            self.assertEqual(request.data, b'{"amount":16.47}')
            self.assertIn("Basic ", request.headers["Authorization"])
            self.assertEqual(make.return_value.open.call_args.kwargs["timeout"], 20)
            self.assertIsInstance(make.call_args.args[0], NoRedirect)
            self.assertEqual(result["amount"], Decimal("16.47"))
        self.assertIsNone(
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid")
        )

    def test_missing_credentials_and_nonallowlisted_paths_stop_before_network(self):
        with patch("urllib.request.build_opener") as make:
            with override_settings(BANQUEST_API_SOURCE_KEY=""):
                with self.assertRaises(ProviderFailure):
                    Gateway()
            make.assert_not_called()
            gateway = Gateway()
            for path in (
                "https://api.banquestgateway.com/api/v2/transactions/charge",
                "../transactions/verify",
                "transactions/verify",
                "transactions/authonly",
            ):
                with self.assertRaises(ProviderFailure):
                    gateway.request("POST", path, {})
            make.return_value.open.assert_not_called()

    def test_http_errors_timeouts_invalid_json_and_large_responses_are_redacted(self):
        for error in (
            TimeoutError("secret-provider-body"),
            urllib.error.HTTPError(BASE, 401, "secret-provider-body", {}, None),
        ):
            with (
                self.subTest(error=type(error).__name__),
                patch("urllib.request.build_opener") as make,
            ):
                make.return_value.open.side_effect = error
                with self.assertRaises(ProviderFailure) as caught:
                    Gateway().request("POST", "transactions/charge", {"amount": Decimal("1")})
                self.assertNotIn("secret", str(caught.exception))
                self.assertEqual(make.return_value.open.call_count, 1)
        for raw in (b"not-json", b"x" * 1048577):
            response = MagicMock()
            response.status = 200
            response.read.return_value = raw
            context = MagicMock()
            context.__enter__.return_value = response
            with patch("urllib.request.build_opener") as make:
                make.return_value.open.return_value = context
                with self.assertRaises(ProviderFailure):
                    Gateway().request("GET", "transactions/1")

    def test_arrival_charge_uses_saved_source_no_hold_no_duplicate_override_or_provider_surcharge(
        self,
    ):
        operation = SimpleNamespace(
            pk=uuid.uuid4(),
            method=SimpleNamespace(state="active", provider_method="123"),
            purpose="arrival",
            amount=Decimal("16.47"),
            allocation=[{"item_tax": ".99", "fee_tax": ".03"}],
        )
        with patch.object(Gateway, "request", return_value={}) as request:
            Gateway().charge(operation)
        method, path, payload = request.call_args.args
        self.assertEqual((method, path), ("POST", "transactions/charge"))
        self.assertEqual(payload["source"], "pm-123")
        self.assertTrue(payload["capture"])
        self.assertFalse(payload["ignore_duplicates"])
        self.assertFalse(payload["save_card"])
        self.assertEqual(payload["amount_details"], {"tax": Decimal("1.02")})
        self.assertEqual(payload["custom_fields"]["custom1"], str(operation.pk))
        self.assertTrue(payload["transaction_flags"]["is_customer_initiated"])
        operation.purpose = "no_show"
        with patch.object(Gateway, "request", return_value={}) as request:
            Gateway().charge(operation)
        self.assertFalse(request.call_args.args[2]["transaction_flags"]["cardholder_present"])

    def test_method_creation_exchanges_nonce_without_a_verification_charge(self):
        with patch.object(Gateway, "request", return_value={"id": 23}) as request:
            Gateway().save_card("12", "nonce-Synthetic", 12, 2035)
        method, path, payload = request.call_args.args
        self.assertEqual((method, path), ("POST", "customers/12/payment-methods"))
        self.assertEqual(
            payload,
            {
                "source": "nonce-Synthetic",
                "expiry_month": 12,
                "expiry_year": 2035,
                "is_default": False,
            },
        )
        self.assertNotIn("amount", payload)
        with self.assertRaises(ValidationError):
            Gateway().save_card("12", "raw-card-not-a-nonce", 12, 2035)
