"""Resend's Svix v1 signature contract; retain only delivery status facts, not raw mail."""

import base64
import hashlib
import hmac
import json
import re
import uuid
from email.utils import parseaddr

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.payments.jobs import enqueue

from .models import MailProviderEvent, MessageDelivery, MessageEvent
from .transport import enabled

KINDS = {
    "email.sent",
    "email.delivered",
    "email.bounced",
    "email.complained",
    "email.failed",
    "email.suppressed",
}


def verify(body, headers):
    key = settings.RESEND_WEBHOOK_SECRET
    event_id, timestamp, signatures = (
        headers.get(name, "") for name in ("svix-id", "svix-timestamp", "svix-signature")
    )
    try:
        if (
            not key.startswith("whsec_")
            or len(body) > 65536
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", event_id)
            or not re.fullmatch(r"[0-9]{1,12}", timestamp)
            or len(signatures) > 2000
            or abs(timezone.now().timestamp() - int(timestamp)) > 300
        ):
            raise ValueError
        encoded = key[6:]
        secret = base64.b64decode(encoded + "=" * (-len(encoded) % 4), validate=True)
        if len(secret) < 16:
            raise ValueError
        expected = (
            "v1,"
            + base64.b64encode(
                hmac.new(
                    secret, (event_id + "." + timestamp + ".").encode() + body, hashlib.sha256
                ).digest()
            ).decode()
        )
        if not any(hmac.compare_digest(expected, value) for value in signatures.split(" ")):
            raise ValueError
    except (ValueError, TypeError):
        raise ValidationError("Invalid email-provider notification.") from None
    return event_id


@transaction.atomic
def receive(body, headers):
    enabled()
    event_id = verify(body, headers)
    try:
        data = json.loads(body)
        if data["type"] not in KINDS:
            return None
        provider_id = str(uuid.UUID(data["data"]["email_id"]))
        message_key = data["data"].get("tags", {}).get("monkeydo_message")
        if message_key:
            message_key = uuid.UUID(message_key)
            scoped = MessageDelivery.objects.filter(pk=message_key).first()
            if (
                scoped is None
                or parseaddr(data["data"].get("from", ""))[1].casefold()
                != parseaddr(settings.DEFAULT_FROM_EMAIL)[1].casefold()
                or data["data"].get("to", []) != [scoped.recipient]
            ):
                raise ValueError
        elif not MessageDelivery.objects.filter(provider_reference=provider_id).exists():
            return None
        when = parse_datetime(data["created_at"])
        if when is None or timezone.is_naive(when):
            raise ValueError
        digest = hashlib.sha256(body).hexdigest()
        event, created = MailProviderEvent.objects.get_or_create(
            event_id=event_id,
            defaults={
                "payload_hash": digest,
                "message_key": message_key,
                "provider_reference": provider_id,
                "event_type": data["type"],
                "occurred_at": when,
            },
        )
        if not created and event.payload_hash != digest:
            raise ValueError
        enqueue(kind="email_event", reference=event.pk, key="email-event:" + event_id)
        return event
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValidationError("Invalid email-provider notification.") from None


@transaction.atomic
def process_event(event_id):
    from .services import notify_issue

    event = MailProviderEvent.objects.get(pk=event_id)
    message = (
        MessageDelivery.objects.select_for_update()
        .filter(provider_reference=event.provider_reference)
        .first()
    )
    if message is None and event.message_key:
        message = (
            MessageDelivery.objects.select_for_update()
            .filter(pk=event.message_key, provider_reference="", state__in=["sending", "unknown"])
            .first()
        )
        if message:
            message.provider_reference = event.provider_reference
            message.save(update_fields=["provider_reference"])
    if message is None:
        raise ValidationError("The provider message reference needs owner review.")
    if message.events.filter(code="provider_event_" + str(event.pk)).exists():
        return
    if event.event_type in {
        "email.bounced",
        "email.complained",
        "email.failed",
        "email.suppressed",
    }:
        state = "bounced"
    elif event.event_type == "email.delivered":
        state = "delivered"
    else:
        state = "sent"
    # Preserve final rejection and a more informative delivered outcome when events arrive out of order.
    if message.state in {"bounced", "failed", "cancelled"} or (
        message.state == "delivered" and state == "sent"
    ):
        return
    message.state, message.code = state, "provider_" + event.event_type.split(".")[1]
    fields = ["state", "code"]
    if state in {"delivered", "bounced"}:
        field = "delivered_at" if state == "delivered" else "bounced_at"
        if getattr(message, field) is None:
            setattr(message, field, event.occurred_at)
            fields.append(field)
    message.save(update_fields=fields)
    MessageEvent.objects.create(
        delivery=message, state=state, code="provider_event_" + str(event.pk)
    )
    if state == "bounced":
        notify_issue(message)


@csrf_exempt
@require_POST
def endpoint(request):
    if not settings.BOOKING_EMAIL_ENABLED or not settings.RESEND_WEBHOOK_SECRET:
        return HttpResponse(status=404)
    try:
        if int(request.META.get("CONTENT_LENGTH") or 0) > 65536:
            return HttpResponse(status=413)
        receive(request.body, request.headers)
    except (ValidationError, ValueError):
        return HttpResponse(status=400)
    return HttpResponse(status=200)
