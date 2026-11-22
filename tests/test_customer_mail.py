"""Durable, truthful customer mail without weakening account-email recipient controls."""

import base64
import hashlib
import json
import uuid
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings

from core.communications.content import booking_confirmation
from core.communications.models import MessageDelivery
from core.communications.services import deliver, enqueue
from core.communications.transport import MailUnavailable, send
from core.models import Customer, DurableJob
from core.waivers.services import SOURCE_HASH
from tests import test_payment_ledger as fixtures


@override_settings(
    BOOKING_EMAIL_ENABLED=True, PAYMENT_SANDBOX_ENABLED=True, RESEND_API_KEY="fake-test-mail-key"
)
class CustomerMailTests(TestCase):
    setUp = fixtures.PaymentLedgerTests.setUp
    create = fixtures.PaymentLedgerTests.create
    sale = fixtures.PaymentLedgerTests.sale

    def message(self, **changes):
        values = {
            "key": str(uuid.uuid4()),
            "kind": "booking_confirmation",
            "recipient": self.customer.email,
            "subject": "Your Monkey Do adventure is booked!",
            "text": "Test booking content",
            "customer": self.customer,
        }
        return enqueue(**(values | changes))

    def test_outbox_is_idempotent_and_not_a_sent_email(self):
        key = str(uuid.uuid4())
        first = self.message(key=key)
        self.assertEqual(self.message(key=key).pk, first.pk)
        self.assertEqual(first.state, "queued")
        self.assertIsNone(first.sent_at)
        self.assertEqual(DurableJob.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.message(key=key, text="Changed content")

    def test_send_success_is_recorded_once_and_does_not_mean_confirmed_inbox_delivery(self):
        message = self.message()
        provider_id = str(uuid.uuid4())
        with patch("core.communications.services.send", return_value=provider_id) as transport:
            first = deliver(message.pk)
            second = deliver(message.pk)
        self.assertEqual(first.state, "sent")
        self.assertEqual(first.sent_at, second.sent_at)
        self.assertIsNotNone(first.sent_at)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(first.provider_reference, provider_id)
        self.assertEqual(first.get_state_display(), "Sent to email provider")

    def test_unknown_result_and_interrupted_send_are_never_automatically_replayed(self):
        message = self.message()
        with patch("core.communications.services.send", side_effect=MailUnavailable()) as transport:
            self.assertEqual(deliver(message.pk).state, "unknown")
            self.assertEqual(deliver(message.pk).state, "unknown")
            self.assertEqual(transport.call_count, 1)
        interrupted = self.message()
        MessageDelivery.objects.filter(pk=interrupted.pk).update(state="sending")
        with patch("core.communications.services.send") as transport:
            self.assertEqual(deliver(interrupted.pk).state, "unknown")
            transport.assert_not_called()

    def test_current_contact_supersedes_unsent_snapshot_without_retargeting_its_history(self):
        message = self.message()
        Customer.objects.filter(pk=self.customer.pk).update(email="updated@example.invalid")
        with patch("core.communications.services.send") as transport:
            self.assertEqual(deliver(message.pk).state, "cancelled")
            transport.assert_not_called()
        refreshed = MessageDelivery.objects.exclude(pk=message.pk).get()
        self.assertEqual(refreshed.recipient, "updated@example.invalid")
        message.refresh_from_db()
        self.assertEqual(message.recipient, "test@example.invalid")
        self.assertEqual(refreshed.state, "queued")

    def test_missing_configuration_leaves_unsent_for_operator_review(self):
        message = self.message()
        with (
            override_settings(RESEND_API_KEY=""),
            patch("core.communications.services.send") as transport,
        ):
            with self.assertRaises(MailUnavailable):
                deliver(message.pk)
            transport.assert_not_called()
        message.refresh_from_db()
        self.assertEqual(message.state, "queued")
        self.assertIsNone(message.dispatched_at)

    def test_any_test_recipient_uses_separate_transport_with_test_banner_and_unsigned_attachment_only(
        self,
    ):
        message = self.message(
            recipient="tester-not-on-account-allowlist@example.invalid", unsigned_waiver=True
        )
        MessageDelivery.objects.filter(pk=message.pk).update(state="sending")
        message.refresh_from_db()
        provider_id = str(uuid.uuid4())
        response = MagicMock()
        response.__enter__.return_value.status = 200
        response.__enter__.return_value.read.return_value = json.dumps({"id": provider_id}).encode()
        with patch("core.communications.transport.build_opener") as opener:
            opener.return_value.open.return_value = response
            self.assertEqual(send(message), provider_id)
        request = opener.return_value.open.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.resend.com/emails")
        self.assertTrue(payload["subject"].startswith("[MONKEYDO TEST]"))
        self.assertIn("not a real visit or payment", payload["text"])
        self.assertEqual(payload["to"], [message.recipient])
        attachment = base64.b64decode(payload["attachments"][0]["content"])
        self.assertEqual(hashlib.sha256(attachment).hexdigest(), SOURCE_HASH)
        self.assertIn(str(message.pk), request.get_header("Idempotency-key"))

    def test_original_message_content_and_final_outcome_cannot_be_overwritten(self):
        message = self.message()
        with self.assertRaises(DatabaseError), transaction.atomic():
            MessageDelivery.objects.filter(pk=message.pk).update(text_body="Overwritten")
        with patch("core.communications.services.send", return_value=str(uuid.uuid4())):
            deliver(message.pk)
        with self.assertRaises(DatabaseError), transaction.atomic():
            MessageDelivery.objects.filter(pk=message.pk).update(state="queued")

    def test_confirmation_uses_final_breakdown_and_does_not_claim_money_was_received(self):
        self.sale(method="zelle", socks=1)
        body = booking_confirmation(self.booking)
        self.assertIn("Your total is $", body)
        self.assertNotIn("Actual payment received", body)
        self.assertIn("Please Zelle payment at any time to monkeydoplay@gmail.com.", body)
        self.assertIn("Sales tax:", body)
        self.assertIn("pick up upon arrival", body)
