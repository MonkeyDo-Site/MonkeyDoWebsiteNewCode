from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from django.core.mail import EmailMessage
from django.test import SimpleTestCase, override_settings

from core.test_email import DeliveryNotConfirmed, StagingEmailBackend, send_to_resend


@override_settings(
    APP_ENV="test",
    RESEND_API_KEY="test-only-not-a-real-key",
    STAGING_EMAIL_RECIPIENTS=("owner@example.invalid",),
    DEFAULT_FROM_EMAIL="bookings@monkeydoplay.com",
)
class StagingEmailTests(SimpleTestCase):
    @patch("core.test_email.send_to_resend")
    def test_only_allowlisted_recipients_and_fixed_sender_can_be_sent(self, send):
        msg = EmailMessage("Your code", "A fictional test code", to=["OWNER@example.invalid"])
        self.assertEqual(StagingEmailBackend().send_messages([msg]), 1)
        payload = send.call_args.args[0]
        self.assertEqual(payload["subject"], "[MONKEYDO TEST] Your code")
        self.assertEqual(payload["from"], "bookings@monkeydoplay.com")
        for message in (
            EmailMessage("No", "No", to=["outsider@example.invalid"]),
            EmailMessage(
                "No", "No", to=["owner@example.invalid"], bcc=["outsider@example.invalid"]
            ),
            EmailMessage(
                "No", "No", from_email="other@example.invalid", to=["owner@example.invalid"]
            ),
        ):
            with self.assertRaises(DeliveryNotConfirmed):
                StagingEmailBackend().send_messages([message])
        self.assertEqual(send.call_count, 1)

    @patch("core.test_email.build_opener")
    def test_provider_timeout_does_not_retry_or_expose_response(self, opener):
        opener.return_value.open.side_effect = URLError("private-provider-detail")
        with self.assertRaises(DeliveryNotConfirmed) as error:
            send_to_resend({"text": "secret-code"})
        self.assertNotIn("private-provider-detail", str(error.exception))
        self.assertEqual(opener.return_value.open.call_count, 1)
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.resend.com/emails")
        self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], 10)

    @patch("core.test_email.build_opener")
    def test_rejection_and_redirect_fail_safely(self, opener):
        for status in (302, 403, 500):
            opener.return_value.open.side_effect = HTTPError(
                "https://api.resend.com/emails", status, "private-detail", {}, None
            )
            with self.assertRaises(DeliveryNotConfirmed):
                send_to_resend({"text": "private"})

    @patch("core.test_email.build_opener")
    def test_success_requires_provider_acknowledgement(self, opener):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"id":"test-message"}'
        opener.return_value.open.return_value.__enter__.return_value = response
        send_to_resend({"text": "test"})
        response.read.return_value = b"{}"
        with self.assertRaises(DeliveryNotConfirmed):
            send_to_resend({"text": "test"})

    @patch("core.test_email.send_to_resend")
    def test_attachments_not_silently_dropped(self, send):
        message = EmailMessage("No", "No", to=["owner@example.invalid"])
        message.attach("test.txt", "test")
        with self.assertRaises(DeliveryNotConfirmed):
            StagingEmailBackend().send_messages([message])
        send.assert_not_called()
