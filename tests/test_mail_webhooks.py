"""Svix raw-body signatures, bounded allowlisted facts and truthful bounce recovery."""

import base64
import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.communications.models import MailProviderEvent, MessageDelivery
from core.communications.services import claim, deliver
from core.communications.webhooks import process_event, receive
from tests import test_customer_mail as fixtures

SECRET = b"synthetic-local-svix-test-key-only"


@override_settings(
    BOOKING_EMAIL_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    RESEND_API_KEY="fake-test-mail-key",
    RESEND_WEBHOOK_SECRET="whsec_" + base64.b64encode(SECRET).decode(),
)
class MailWebhookTests(TestCase):
    setUp = fixtures.CustomerMailTests.setUp
    message = fixtures.CustomerMailTests.message

    def signed(self, data, event_id=None, seconds=0):
        body = json.dumps(data).encode()
        event_id = event_id or "msg_" + uuid.uuid4().hex
        stamp = str(int((timezone.now() + timedelta(seconds=seconds)).timestamp()))
        signature = base64.b64encode(
            hmac.new(
                SECRET, (event_id + "." + stamp + ".").encode() + body, hashlib.sha256
            ).digest()
        ).decode()
        return body, {
            "svix-id": event_id,
            "svix-timestamp": stamp,
            "svix-signature": "v1," + signature,
        }

    def evidence(self, message, provider_id, kind="email.bounced", tags=False):
        values = {
            "email_id": provider_id,
            "to": [message.recipient],
            "from": settings.DEFAULT_FROM_EMAIL,
            "subject": "private message body must not persist",
            "bounce": {"message": "arbitrary provider details"},
        }
        if tags:
            values["tags"] = {"monkeydo_message": str(message.pk)}
        return {"type": kind, "created_at": timezone.now().isoformat(), "data": values}

    def test_bounce_is_verified_deduplicated_and_alert_goes_to_owner_not_customer(self):
        message = self.message()
        provider_id = str(uuid.uuid4())
        with patch("core.communications.services.send", return_value=provider_id):
            deliver(message.pk)
        body, headers = self.signed(self.evidence(message, provider_id))
        event = receive(body, headers)
        self.assertEqual(receive(body, headers).pk, event.pk)
        process_event(event.pk)
        process_event(event.pk)
        message.refresh_from_db()
        self.assertEqual(message.state, "bounced")
        self.assertIsNotNone(message.bounced_at)
        alert = MessageDelivery.objects.get(kind="email_issue")
        self.assertEqual(alert.recipient, settings.BOOKING_REPLY_TO)
        self.assertEqual(claim(alert.pk).recipient, settings.BOOKING_REPLY_TO)
        self.assertEqual(MailProviderEvent.objects.count(), 1)
        self.assertNotIn("subject", {field.name for field in MailProviderEvent._meta.fields})
        self.assertNotIn("bounce", {field.name for field in MailProviderEvent._meta.fields})

    def test_tampered_or_stale_notifications_cannot_change_delivery_state(self):
        message = self.message()
        provider_id = str(uuid.uuid4())
        for seconds in [-301, 301]:
            body, headers = self.signed(self.evidence(message, provider_id), seconds=seconds)
            with self.assertRaises(ValidationError):
                receive(body, headers)
        body, headers = self.signed(self.evidence(message, provider_id))
        with self.assertRaises(ValidationError):
            receive(body + b" ", headers)
        self.assertFalse(MailProviderEvent.objects.exists())

    def test_signed_tag_can_reconcile_an_unknown_send_without_sending_again(self):
        message = self.message()
        MessageDelivery.objects.filter(pk=message.pk).update(state="unknown")
        provider_id = str(uuid.uuid4())
        body, headers = self.signed(
            self.evidence(message, provider_id, kind="email.delivered", tags=True)
        )
        event = receive(body, headers)
        with patch("core.communications.services.send") as send:
            process_event(event.pk)
            deliver(message.pk)
        send.assert_not_called()
        message.refresh_from_db()
        self.assertEqual(message.state, "delivered")
        self.assertEqual(message.provider_reference, provider_id)
        self.assertIsNone(message.sent_at)
        self.assertIsNotNone(message.delivered_at)

    def test_signed_but_wrong_recipient_tag_does_not_link_to_a_local_message(self):
        message = self.message()
        data = self.evidence(message, str(uuid.uuid4()), tags=True)
        data["data"]["to"] = ["different@example.invalid"]
        body, headers = self.signed(data)
        with self.assertRaises(ValidationError):
            receive(body, headers)
        self.assertFalse(MailProviderEvent.objects.exists())

    def test_only_exact_enabled_post_callback_bypasses_private_staging_gate(self):
        with override_settings(APP_ENV="staging"):
            client = Client()
            response = client.post(
                "/integrations/resend/webhook/", b"{}", content_type="application/json", secure=True
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                client.get("/integrations/resend/webhook/", secure=True).status_code, 302
            )
            self.assertEqual(
                client.post(
                    "/integrations/resend/webhook/other/",
                    b"{}",
                    content_type="application/json",
                    secure=True,
                ).status_code,
                302,
            )
