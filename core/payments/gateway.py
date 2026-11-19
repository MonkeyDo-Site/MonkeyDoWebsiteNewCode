"""Banquest v2 sandbox only. Exact JSON cents, no retries, redirects or raw card fields."""

import base64
import json
import re
import urllib.error
import urllib.request
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from .amounts import amount
from .ledger import enabled

BASE = "https://api.sandbox.banquestgateway.com/api/v2/"
MAX_RESPONSE = 1024 * 1024


class ProviderFailure(Exception):
    def __init__(self, code="provider_outcome_unknown"):
        self.code = code
        super().__init__("The payment provider requires review. No automatic retry was made.")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def exact_json(value):
    if isinstance(value, Decimal):
        return format(amount(value), "f")
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(k) + ":" + exact_json(v) for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(exact_json(v) for v in value) + "]"
    if isinstance(value, float):
        raise ValidationError("Do not encode currency as binary floating point.")
    return json.dumps(value, ensure_ascii=True)


def reference(value):
    if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]{0,19}", str(value)):
        raise ProviderFailure("invalid_provider_reference")
    return str(value)


class Gateway:
    def __init__(self):
        enabled()
        if not settings.BANQUEST_API_SOURCE_KEY:
            raise ProviderFailure("sandbox_credentials_missing")
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, payload=None):
        if not re.fullmatch(
            r"(transactions/(charge|refund|void|[1-9][0-9]*)|customers(/[1-9][0-9]*/payment-methods)?|payment-methods/[1-9][0-9]*)",
            path,
        ):
            raise ProviderFailure("unsupported_provider_path")
        credentials = base64.b64encode(
            (settings.BANQUEST_API_SOURCE_KEY + ":" + settings.BANQUEST_API_PIN).encode()
        ).decode()
        request = urllib.request.Request(
            BASE + path,
            data=exact_json(payload).encode() if payload is not None else None,
            method=method,
            headers={
                "Authorization": "Basic " + credentials,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "MonkeyDo-Staging/1.0",
            },
        )
        try:
            with self.opener.open(request, timeout=20) as response:
                if not 200 <= response.status < 300:
                    raise ProviderFailure()
                raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise ProviderFailure("provider_response_too_large")
                data = json.loads(raw, parse_float=Decimal)
                if not isinstance(data, (dict, list)):
                    raise ProviderFailure("invalid_provider_response")
                return data
        except ProviderFailure:
            raise
        except (OSError, urllib.error.URLError, ValueError, TypeError):
            # HTTP errors can contain request/card data. Never propagate bodies,
            # credentials, URLs or provider text to logs, audit or user errors.
            raise ProviderFailure() from None

    def charge(self, operation):
        method = operation.method
        if not method or method.state != "active" or not method.provider_method:
            raise ProviderFailure("payment_method_unavailable")
        payload = {
            "source": "pm-" + reference(method.provider_method),
            "amount": amount(operation.amount),
            "capture": True,
            "save_card": False,
            "ignore_duplicates": False,
            "amount_details": {
                "tax": sum(
                    (amount(p["item_tax"]) + amount(p["fee_tax"]) for p in operation.allocation),
                    Decimal("0.00"),
                )
            },
            "custom_fields": {"custom1": str(operation.pk), "custom2": "monkeydo:sandbox"},
            "transaction_details": {"description": "MonkeyDo sandbox payment " + str(operation.pk)},
            "transaction_flags": {
                "allow_partial_approval": False,
                "is_recurring": False,
                "is_installment": False,
                "is_customer_initiated": operation.purpose == "arrival",
                "cardholder_present": operation.purpose == "arrival",
                "card_present": False,
            },
        }
        return self.request("POST", "transactions/charge", payload)

    def refund(self, operation):
        return self.request(
            "POST",
            "transactions/refund",
            {
                "reference_number": int(reference(operation.original.provider_reference)),
                "amount": amount(operation.amount),
                "custom_fields": {"custom1": str(operation.pk), "custom2": "monkeydo:sandbox"},
            },
        )

    def void(self, operation):
        return self.request(
            "POST",
            "transactions/void",
            {"reference_number": int(reference(operation.original.provider_reference))},
        )

    def transaction(self, transaction_id):
        return self.request("GET", "transactions/" + reference(transaction_id))

    def create_customer(self, setup_id):
        # Stable setup identity is reconciliation evidence, not an idempotency
        # promise. A lost POST response must be reconciled, never blindly replayed.
        identity = "md-" + str(uuid.UUID(str(setup_id)))
        return self.request(
            "POST",
            "customers",
            {"identifier": "MonkeyDo sandbox " + identity, "customer_number": identity},
        )

    def save_card(self, provider_customer, nonce, expiry_month, expiry_year):
        if not isinstance(nonce, str) or not re.fullmatch(r"nonce-[A-Za-z0-9]{1,20}", nonce):
            raise ValidationError("Use the secure provider card-entry form.")
        now = timezone.localtime()
        if (
            type(expiry_month) is not int
            or type(expiry_year) is not int
            or not 1 <= expiry_month <= 12
            or not now.year <= expiry_year <= now.year + 30
            or (expiry_year, expiry_month) < (now.year, now.month)
        ):
            raise ValidationError("The entered card has expired or has an invalid expiry.")
        # Expiry is used transiently for the provider exchange, never stored.
        return self.request(
            "POST",
            f"customers/{reference(provider_customer)}/payment-methods",
            {
                "source": nonce,
                "expiry_month": expiry_month,
                "expiry_year": expiry_year,
                "is_default": False,
            },
        )

    def method(self, method_id):
        return self.request("GET", "payment-methods/" + reference(method_id))

    def delete_method(self, method_id):
        return self.request("DELETE", "payment-methods/" + reference(method_id))
