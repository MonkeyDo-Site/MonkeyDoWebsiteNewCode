"""Explicitly configured, allowlisted staging delivery through Resend; never retries."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail.backends.base import BaseEmailBackend
from django.core.validators import validate_email


class DeliveryNotConfirmed(Exception):
    """Safe caller-facing exception; never includes provider body, message or credential."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send_to_resend(payload):
    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + settings.RESEND_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "MonkeyDo-staging/1",
        },
        method="POST",
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=10) as response:
            data = json.loads(response.read(65536))
            if (
                response.status not in (200, 201)
                or not isinstance(data, dict)
                or not data.get("id")
            ):
                raise DeliveryNotConfirmed("Email delivery could not be confirmed.")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        raise DeliveryNotConfirmed("Email delivery could not be confirmed.") from None


class StagingEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        count = 0
        for message in email_messages or []:
            try:
                recipients = message.recipients()
                if (
                    settings.APP_ENV not in {"staging", "test"}
                    or not settings.RESEND_API_KEY
                    or not recipients
                    or message.attachments
                    or message.from_email != settings.DEFAULT_FROM_EMAIL
                ):
                    raise DeliveryNotConfirmed("Staging email configuration is incomplete.")
                allowlist = {x.casefold() for x in settings.STAGING_EMAIL_RECIPIENTS}
                for recipient in recipients:
                    try:
                        validate_email(recipient)
                    except ValidationError:
                        raise DeliveryNotConfirmed(
                            "Only approved test recipients may receive staging email."
                        ) from None
                    if recipient.casefold() not in allowlist:
                        raise DeliveryNotConfirmed(
                            "Only approved test recipients may receive staging email."
                        )
                if "\r" in message.subject or "\n" in message.subject:
                    raise DeliveryNotConfirmed("Invalid email subject.")
                payload = {
                    "from": settings.DEFAULT_FROM_EMAIL,
                    "to": message.to,
                    "subject": "[MONKEYDO TEST] "
                    + message.subject.removeprefix("[MONKEYDO TEST] "),
                    "text": message.body,
                }
                if message.cc:
                    payload["cc"] = message.cc
                if message.bcc:
                    payload["bcc"] = message.bcc
                if message.reply_to:
                    payload["reply_to"] = message.reply_to
                for alternative in getattr(message, "alternatives", []):
                    if alternative[1] == "text/html":
                        payload["html"] = alternative[0]
                send_to_resend(payload)
                count += 1
            except DeliveryNotConfirmed:
                if not self.fail_silently:
                    raise
        return count
