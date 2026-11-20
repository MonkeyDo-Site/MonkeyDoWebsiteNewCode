"""A recovered snapshot cannot replay a queued charge, card action or email."""

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.communications.services import deliver, enqueue
from core.communications.transport import MailUnavailable
from core.payments.operations import execute
from tests import test_payment_ledger as fixtures


@override_settings(
    PAYMENT_SANDBOX_ENABLED=True, BOOKING_EMAIL_ENABLED=True, CUSTOMER_TEST_BOOKING=True
)
class RecoveryHoldTests(TestCase):
    setUp = fixtures.PaymentLedgerTests.setUp
    create = fixtures.PaymentLedgerTests.create
    sale = fixtures.PaymentLedgerTests.sale
    operation = fixtures.PaymentLedgerTests.operation

    def test_ready_operation_is_not_dispatched_and_worker_does_not_claim_jobs(self):
        operation = self.operation(self.sale())
        with (
            override_settings(RECOVERY_HOLD=True),
            patch("core.payments.operations.Gateway") as gateway,
        ):
            with self.assertRaises(ValidationError):
                execute(operation.pk)
            with self.assertRaises(CommandError):
                call_command("run_payment_jobs")
            gateway.assert_not_called()
        operation.refresh_from_db()
        self.assertEqual(operation.state, "ready")
        self.assertIsNone(operation.dispatched_at)

    def test_email_stays_unsent_and_public_booking_forms_pause(self):
        message = enqueue(
            key="recovery-hold-fixture",
            kind="booking_confirmation",
            recipient=self.customer.email,
            subject="Synthetic booking",
            text="Fictional recovery test",
            customer=self.customer,
        )
        with (
            override_settings(RECOVERY_HOLD=True),
            patch("core.communications.services.send") as send,
        ):
            with self.assertRaises(MailUnavailable):
                deliver(message.pk)
            send.assert_not_called()
            response = self.client.get("/book/complete/email/")
            self.assertEqual(response.status_code, 503)
            self.assertContains(response, "Bookings are temporarily paused", status_code=503)
        message.refresh_from_db()
        self.assertEqual(message.state, "queued")
