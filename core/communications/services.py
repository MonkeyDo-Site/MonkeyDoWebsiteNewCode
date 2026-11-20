"""Immutable message snapshots with an explicit durable delivery attempt."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import AuditEvent
from core.payments.ledger import fingerprint

from .models import MessageDelivery, MessageEvent
from .transport import MailUnavailable, enabled, send


@transaction.atomic
def enqueue(
    *,
    key,
    kind,
    recipient,
    subject,
    text,
    customer=None,
    booking=None,
    unsigned_waiver=False,
    actor=None,
):
    enabled()
    if kind not in dict(MessageDelivery._meta.get_field("kind").choices) or len(text) > 65536:
        raise ValidationError("Unsupported customer message.")
    data = {
        "kind": kind,
        "recipient": recipient,
        "subject": subject,
        "text_body": text,
        "unsigned_waiver": unsigned_waiver,
        "customer_id": customer.pk if customer else None,
        "booking_id": booking.pk if booking else None,
        "template_version": "MD-EMAIL-2026-01",
    }
    message, created = MessageDelivery.objects.get_or_create(
        dedupe_key=key, defaults=data | {"fingerprint": fingerprint(data), "actor": actor}
    )
    if not created and message.fingerprint != fingerprint(data):
        raise ValidationError("This message key already identifies different content.")
    if created:
        MessageEvent.objects.create(delivery=message, state="queued", actor=actor)
    from core.payments.jobs import enqueue as enqueue_job

    enqueue_job(kind="customer_email", reference=message.pk, key="email:" + str(message.pk))
    return message


@transaction.atomic
def claim(message_id):
    # Lock this attempt only; its optional customer uses a nullable outer join.
    message = MessageDelivery.objects.select_for_update().get(pk=message_id)
    if message.state != "queued":
        if message.state == "sending":
            message.state = "unknown"
            message.code = "interrupted_mail"
            message.save(update_fields=["state", "code"])
            MessageEvent.objects.create(delivery=message, state="unknown", code=message.code)
        return None
    if (
        message.kind != "payment_issue"
        and message.customer_id
        and message.customer.email.casefold() != message.recipient.casefold()
    ):
        message.state = "cancelled"
        message.code = "contact_changed"
        message.save(update_fields=["state", "code"])
        MessageEvent.objects.create(delivery=message, state="cancelled", code=message.code)
        if message.customer.email:
            enqueue(
                key="contact-refresh:" + str(message.pk),
                kind=message.kind,
                recipient=message.customer.email,
                subject=message.subject,
                text=message.text_body,
                customer=message.customer,
                booking=message.booking,
                unsigned_waiver=message.unsigned_waiver,
                actor=message.actor,
            )
        return None
    if not settings.RESEND_API_KEY:
        # This job can be explicitly resumed after configuration; nothing was sent.
        raise MailUnavailable("mail_configuration")
    message.state = "sending"
    message.dispatched_at = timezone.now()
    message.save(update_fields=["state", "dispatched_at"])
    MessageEvent.objects.create(delivery=message, state="sending")
    return message


def deliver(message_id):
    enabled()
    message = claim(message_id)
    if message is None:
        return MessageDelivery.objects.get(pk=message_id)
    reference = ""
    try:
        reference = send(message)
        state, code = "sent", ""
    except MailUnavailable as error:
        state = (
            "failed"
            if error.code
            in {
                "mail_rejected",
                "mail_recipient",
                "mail_header",
                "mail_attachment",
                "mail_configuration",
            }
            else "unknown"
        )
        code = error.code
    with transaction.atomic():
        current = MessageDelivery.objects.select_for_update().get(pk=message_id)
        if current.state != "sending":
            return current
        current.state, current.code, current.provider_reference = state, code, reference
        current.sent_at = timezone.now() if state == "sent" else None
        current.save(update_fields=["state", "code", "provider_reference", "sent_at"])
        MessageEvent.objects.create(delivery=current, state=state, code=code)
        AuditEvent.objects.create(
            actor=None,
            action="message." + state,
            record_type="message",
            record_id=str(current.pk),
            changes={"kind": current.kind, "booking_id": current.booking_id},
        )
        return current


@transaction.atomic
def resend_confirmation(*, actor, message_id, request_key):
    from django.urls import reverse

    from core.payments.ledger import lock_request
    from core.permissions import require_actor
    from core.waivers.services import create_share

    from .content import booking_confirmation

    enabled()
    for permission in (
        "core.change_booking",
        "core.view_booking",
        "core.view_customer",
        "core.view_messagedelivery",
    ):
        require_actor(actor, permission)
    key = lock_request(request_key)
    original = MessageDelivery.objects.select_related("booking__customer", "customer").get(
        pk=message_id
    )
    if (
        original.kind not in {"booking_confirmation", "booking_waiver"}
        or original.booking_id is None
    ):
        raise ValidationError("Only a booking confirmation can be resent here.")
    dedupe = "resend:" + str(key)
    previous = MessageDelivery.objects.filter(dedupe_key=dedupe).first()
    if previous:
        if previous.booking_id != original.booking_id or previous.actor_id != actor.pk:
            raise ValidationError("This resend request was already used for another confirmation.")
        return previous
    customer = original.booking.customer
    if not customer.email:
        raise ValidationError("Add a current customer email address before sending a confirmation.")
    waiver_url = None
    waiver_type = "single"
    if original.kind == "booking_waiver":
        _, token = create_share(actor=actor, booking_id=original.booking_id)
        waiver_url = settings.BOOKING_STAGING_ORIGIN + reverse("shared_waiver", args=[token])
        if original.unsigned_waiver:
            waiver_type = (
                "online_shared" if original.booking.source == "customer_test" else "multiple"
            )
    return enqueue(
        key=dedupe,
        kind=original.kind,
        recipient=customer.email,
        subject=original.subject,
        text=booking_confirmation(original.booking, waiver_url=waiver_url, waiver_type=waiver_type),
        customer=customer,
        booking=original.booking,
        unsigned_waiver=original.unsigned_waiver,
        actor=actor,
    )
