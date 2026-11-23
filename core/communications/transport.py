"""Bounded Resend adapter for approved tester-entered recipients; account rules stay intact."""

import base64
import hashlib
import json
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.views.decorators.debug import sensitive_variables

from core.test_email import NoRedirect
from core.waivers.services import SOURCE_HASH


class MailUnavailable(Exception):
    def __init__(self, code="mail_outcome_unknown"):
        self.code = code
        super().__init__("Email sending could not be confirmed.")


def enabled():
    if not settings.BOOKING_EMAIL_ENABLED or settings.APP_ENV not in {
        "test",
        "development",
        "staging",
    }:
        raise ValidationError("Staging customer email is not enabled.")


@sensitive_variables()
def send(delivery):
    enabled()
    if not settings.RESEND_API_KEY or delivery.state != "sending":
        raise MailUnavailable("mail_configuration")
    try:
        validate_email(delivery.recipient)
    except ValidationError:
        raise MailUnavailable("mail_recipient") from None
    if any(x in delivery.subject + delivery.recipient for x in ("\r", "\n")):
        raise MailUnavailable("mail_header")
    payload = {
        "from": settings.DEFAULT_FROM_EMAIL,
        "to": [delivery.recipient],
        "tags": [{"name": "monkeydo_message", "value": str(delivery.pk)}],
        "reply_to": settings.BOOKING_REPLY_TO,
        "subject": "[MONKEYDO TEST] " + delivery.subject.removeprefix("[MONKEYDO TEST] "),
        "text": "MONKEYDO STAGING TEST — This is a test booking, not a real visit or payment.\n\n"
        + delivery.text_body,
    }
    if delivery.template_version == "MD-EMAIL-2026-02" and delivery.kind in {
        "booking_confirmation",
        "booking_waiver",
        "booking_cancelled",
        "booking_no_show",
    }:
        from .presentation import confirmation_html

        payload["html"] = confirmation_html(delivery.text_body)
    if delivery.unsigned_waiver:
        source = settings.BASE_DIR / "docs" / "waivers" / "source" / "MD Waiver (1).pdf"
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != SOURCE_HASH:
            raise MailUnavailable("mail_attachment")
        payload["attachments"] = [
            {"filename": "MonkeyDo-unsigned-waiver.pdf", "content": base64.b64encode(data).decode()}
        ]
    request = Request(
        "https://api.resend.com/emails",
        method="POST",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + settings.RESEND_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "MonkeyDo-Staging/1.0",
            "Idempotency-Key": "monkeydo-message-" + str(delivery.pk),
        },
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(65537)
            if response.status not in {200, 201} or len(raw) > 65536:
                raise MailUnavailable()
            result = json.loads(raw)
            return str(uuid.UUID(result["id"]))
    except HTTPError as error:
        # Rejected requests are distinct from a possibly accepted lost response.
        code = (
            "mail_rejected" if error.code in {400, 401, 403, 422, 429} else "mail_outcome_unknown"
        )
        raise MailUnavailable(code) from None
    except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
        raise MailUnavailable() from None
