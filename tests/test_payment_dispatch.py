"""Interrupted jobs, signed callbacks and uncertain financial requests never replay charges."""

import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.models import DurableJob, FinancialPosting, PaymentOperation, ProviderEvent
from core.payments.gateway import ProviderFailure
from core.payments.jobs import claim, enqueue, finish, run_one
from core.payments.operations import execute, reconcile
from core.payments.webhooks import receive
from tests import test_payment_ledger as fixtures


@override_settings(
    PAYMENT_SANDBOX_ENABLED=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox-key",
    BANQUEST_API_PIN="fake-pin",
    BANQUEST_WEBHOOK_KEY="fake-webhook-signature",
)
class DispatchTests(TestCase):
    setUp = fixtures.PaymentLedgerTests.setUp
    create = fixtures.PaymentLedgerTests.create
    sale = fixtures.PaymentLedgerTests.sale
    operation = fixtures.PaymentLedgerTests.operation

    def evidence(self, operation, **changes):
        return {
            "id": 451,
            "amount_details": {"amount": operation.amount},
            "transaction_details": {"type": "charge"},
            "status_details": {"status": "captured"},
            "custom_fields": {"custom1": str(operation.pk), "custom2": "monkeydo:sandbox"},
        } | changes

    def test_success_reconciles_actual_amount_and_dispatches_only_once(self):
        operation = self.operation(self.sale())
        with patch("core.payments.operations.Gateway") as gateway:
            gateway.return_value.charge.return_value = {"status_code": "A", "reference_number": 451}
            gateway.return_value.transaction.return_value = self.evidence(operation)
            self.assertEqual(execute(operation.pk).state, "succeeded")
            self.assertEqual(execute(operation.pk).state, "succeeded")
            self.assertEqual(gateway.return_value.charge.call_count, 1)
        self.assertEqual(FinancialPosting.objects.count(), 1)

    def test_timeout_and_worker_restart_never_resend_financial_post(self):
        operation = self.operation(self.sale())
        with patch("core.payments.operations.Gateway") as gateway:
            gateway.return_value.charge.side_effect = ProviderFailure()
            self.assertEqual(execute(operation.pk).state, "unknown")
            self.assertEqual(execute(operation.pk).state, "unknown")
            self.assertEqual(gateway.return_value.charge.call_count, 1)
        self.assertFalse(FinancialPosting.objects.exists())
        with self.assertRaises(ValidationError):
            self.operation(operation.sale)

    def test_changed_provider_amount_or_identity_cannot_mark_paid(self):
        operation = self.operation(self.sale())
        for changes in (
            {"amount_details": {"amount": Decimal("17.00")}},
            {"custom_fields": {"custom1": str(uuid.uuid4())}},
            {"status_details": {"status": "approved"}},
        ):
            with (
                self.subTest(changes=changes),
                patch("core.payments.operations.Gateway") as gateway,
            ):
                gateway.return_value.charge.return_value = {
                    "status_code": "A",
                    "reference_number": 451,
                }
                gateway.return_value.transaction.return_value = self.evidence(operation, **changes)
                if operation.state == "ready":
                    execute(operation.pk)
                else:
                    reconcile(operation_id=operation.pk)
                operation.refresh_from_db()
                self.assertEqual(operation.state, "unknown")
                self.assertFalse(FinancialPosting.objects.exists())

    def test_decline_is_final_and_does_not_post_or_repeat(self):
        operation = self.operation(self.sale())
        with patch("core.payments.operations.Gateway") as gateway:
            gateway.return_value.charge.return_value = {"status_code": "D"}
            self.assertEqual(execute(operation.pk).state, "declined")
            execute(operation.pk)
            self.assertEqual(gateway.return_value.charge.call_count, 1)
        self.assertFalse(FinancialPosting.objects.exists())

    def test_lease_recovery_blocks_interrupted_dispatch_without_another_post(self):
        operation = self.operation(self.sale())
        job = enqueue(
            kind="payment_dispatch", reference=operation.pk, key="dispatch:" + str(operation.pk)
        )
        claimed = claim()
        self.assertEqual(claimed.pk, job.pk)
        PaymentOperation.objects.filter(pk=operation.pk).update(
            state="sending", dispatched_at=timezone.now()
        )
        DurableJob.objects.filter(pk=job.pk).update(
            lease_until=timezone.now() - timedelta(seconds=1)
        )
        with patch("core.payments.operations.Gateway") as gateway:
            self.assertTrue(run_one())
            gateway.assert_not_called()
        operation.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(operation.state, "unknown")
        self.assertEqual(job.state, "blocked")
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertEqual(finish(claimed, "done"), 0)

    def payload(self, operation, event_id="event-one"):
        return json.dumps(
            {
                "id": event_id,
                "event": "transaction",
                "type": "succeeded",
                "timestamp": timezone.now().isoformat(),
                "data": {
                    "reference_number": 451,
                    "transaction": {
                        "custom_fields": {"custom1": str(operation.pk)},
                        "amount_details": {"amount": str(operation.amount)},
                    },
                },
            }
        ).encode()

    def sign(self, body):
        return hmac.new(b"fake-webhook-signature", body, hashlib.sha256).hexdigest()

    def test_webhook_requires_signature_deduplicates_and_never_stores_raw_payload(self):
        operation = self.operation(self.sale())
        body = self.payload(operation)
        with self.assertRaises(ValidationError):
            receive(body, "0" * 64)
        first = receive(body, self.sign(body))
        self.assertEqual(receive(body, self.sign(body)).pk, first.pk)
        self.assertEqual(ProviderEvent.objects.count(), 1)
        self.assertEqual(DurableJob.objects.count(), 1)
        self.assertEqual(set(first.facts), {"operation", "amount"})
        self.assertFalse(FinancialPosting.objects.exists())
        changed = body.replace(b"451", b"452")
        with self.assertRaises(ValidationError):
            receive(changed, self.sign(changed))

    def test_exact_callback_bypasses_private_gate_but_still_requires_signature_and_post(self):
        client = Client(enforce_csrf_checks=True)
        with override_settings(APP_ENV="staging", SECURE_SSL_REDIRECT=False):
            self.assertEqual(
                client.post(
                    "/integrations/banquest/webhook/",
                    data=b"{}",
                    content_type="application/json",
                    secure=True,
                ).status_code,
                400,
            )
            self.assertEqual(
                client.get("/integrations/banquest/webhook/", secure=True).status_code, 302
            )
            response = client.post(
                "/integrations/banquest/webhook/extra/",
                data=b"{}",
                content_type="application/json",
                secure=True,
            )
            self.assertEqual(response.status_code, 302)
        with override_settings(PAYMENT_SANDBOX_ENABLED=False):
            self.assertEqual(
                client.post(
                    "/integrations/banquest/webhook/", data=b"{}", content_type="application/json"
                ).status_code,
                404,
            )

    def test_provider_receipt_and_settlement_dates_are_retained_when_processed_later(self):
        operation = self.operation(self.sale())
        data = self.evidence(
            operation, created_at="2027-01-31T23:59:50-05:00", settled_date="2027-02-02"
        )
        with patch("core.payments.operations.Gateway") as gateway:
            gateway.return_value.charge.return_value = {"status_code": "A", "reference_number": 451}
            gateway.return_value.transaction.return_value = data
            execute(operation.pk)
        posting = FinancialPosting.objects.get()
        self.assertEqual(timezone.localtime(posting.occurred_at).date().isoformat(), "2027-01-31")
        observation = operation.observations.get()
        self.assertEqual(observation.settled_date.isoformat(), "2027-02-02")
        self.assertGreater(posting.recorded_at, posting.occurred_at)

    def test_revoked_actor_cannot_dispatch_an_already_requested_charge(self):
        operation = self.operation(self.sale())
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        from django.core.exceptions import PermissionDenied

        with patch("core.payments.operations.Gateway") as gateway:
            with self.assertRaises(PermissionDenied):
                execute(operation.pk)
            gateway.return_value.charge.assert_not_called()
        self.assertFalse(FinancialPosting.objects.exists())

    def test_signed_but_malformed_provider_reference_is_a_bounded_bad_request(self):
        operation = self.operation(self.sale())
        body = self.payload(operation).replace(b"451", b"0")
        response = self.client.post(
            "/integrations/banquest/webhook/",
            data=body,
            content_type="application/json",
            HTTP_X_SIGNATURE=self.sign(body),
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ProviderEvent.objects.exists())
