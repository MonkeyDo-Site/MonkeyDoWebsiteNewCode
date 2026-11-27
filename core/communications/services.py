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
    membership=None,
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
        "template_version": "MD-EMAIL-2026-03",
    }
    if membership is not None:
        if customer is None or membership.customer_id != customer.pk:
            raise ValidationError("The membership message belongs to another customer.")
        data["membership_id"] = membership.pk
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
    notice_kinds = {"membership_expiry_notice", "membership_grace_notice"}
    confirmation_kinds = {"membership_confirmation", "membership_renewal", "membership_addition"}
    scope = MessageDelivery.objects.only("kind", "customer_id", "membership_id").get(pk=message_id)
    if (scope.kind in notice_kinds or scope.membership_id) and scope.customer_id:
        from core.membership_reservations import lock_customer

        lock_customer(scope.customer_id)
    # Lock this attempt only; its optional customer uses a nullable outer join.
    message = MessageDelivery.objects.select_for_update().get(pk=message_id)
    if message.state != "queued":
        if message.state == "sending":
            message.state = "unknown"
            message.code = "interrupted_mail"
            message.save(update_fields=["state", "code"])
            MessageEvent.objects.create(delivery=message, state="unknown", code=message.code)
        return None
    if message.kind in confirmation_kinds and message.membership_id:
        from core.membership_funding import member_needs_review

        if member_needs_review(message.membership):
            message.state, message.code = "cancelled", "membership_funding_review"
            message.save(update_fields=["state", "code"])
            MessageEvent.objects.create(delivery=message, state="cancelled", code=message.code)
            return None
    if message.kind in notice_kinds:
        from core.membership_records import MembershipRenewalNoticeDelivery
        from core.membership_renewal_notices import refresh_notice

        evidence = (
            MembershipRenewalNoticeDelivery.objects.select_related("notice")
            .filter(message=message)
            .first()
        )
        if evidence is None:
            message.state, message.code = "cancelled", "membership_notice_invalid"
            message.save(update_fields=["state", "code"])
            MessageEvent.objects.create(delivery=message, state="cancelled", code=message.code)
            return None
        refreshed = refresh_notice(evidence.notice)
        if refreshed is None or refreshed.pk != message.pk:
            return None
    if message.kind == "membership_cancellation" and message.membership_id:
        from core.membership_cancellations import queue_cancellation

        cancellation = message.membership.cancellations.order_by("-created_at").first()
        if cancellation:
            refreshed = queue_cancellation(cancellation, initial=False)
            if refreshed and refreshed.pk != message.pk:
                return None
    if (
        message.kind not in {"payment_issue", "email_issue", "backup_alert"}
        and message.customer_id
        and message.customer.email.casefold() != message.recipient.casefold()
    ):
        message.state = "cancelled"
        message.code = "contact_changed"
        message.save(update_fields=["state", "code"])
        MessageEvent.objects.create(delivery=message, state="cancelled", code=message.code)
        replacement_exists = (
            MessageDelivery.objects.exclude(pk=message.pk)
            .filter(
                booking_id=message.booking_id,
                customer=message.customer,
                kind=message.kind,
                recipient__iexact=message.customer.email,
                state__in=["queued", "sending", "sent", "delivered"],
                created_at__gte=message.created_at,
            )
            .exists()
            if message.booking_id
            else False
        )
        if message.customer.email and not replacement_exists:
            enqueue(
                key="contact-refresh:" + str(message.pk),
                kind=message.kind,
                recipient=message.customer.email,
                subject=message.subject,
                text=message.text_body,
                customer=message.customer,
                booking=message.booking,
                membership=message.membership,
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
    if settings.RECOVERY_HOLD:
        raise MailUnavailable("recovery_hold")
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
        if state in {"failed", "unknown"}:
            notify_issue(current)
        return current


@transaction.atomic
def resend_confirmation(*, actor, message_id, request_key):
    from django.urls import reverse

    from core.payments.ledger import lock_request
    from core.permissions import require_actor
    from core.waivers.services import create_share

    from .content import booking_confirmation, session_subject

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
        subject=session_subject(original.booking),
        text=booking_confirmation(original.booking, waiver_url=waiver_url, waiver_type=waiver_type),
        customer=customer,
        booking=original.booking,
        unsigned_waiver=original.unsigned_waiver,
        actor=actor,
    )


def notify_issue(message):
    if message.kind in {"email_issue", "payment_issue", "backup_alert"}:
        return
    try:
        enqueue(
            key="email-issue:" + str(message.pk),
            kind="email_issue",
            recipient=settings.BOOKING_REPLY_TO,
            subject="MonkeyDo booking email requires review",
            text="A sandbox customer email failed, bounced or has an unknown sending outcome. Recipient: "
            + message.recipient
            + ". Review the protected Messages page. Booking: "
            + str(message.booking_id or "not linked")
            + ". No automatic resend will be made.",
            customer=message.customer,
            booking=message.booking,
        )
    except Exception:
        # Message state/history is the persistent fallback if the alert cannot queue.
        pass


@transaction.atomic
def enqueue_closure(*, booking, checkout, actor):
    from core.date_display import display_date
    from core.payments.checkout import summary
    from core.payments.zelle import facts

    state = summary(booking)
    zelle = facts(booking)
    cancelled = checkout.kind == "cancellation"
    lines = [
        f"Dear Family {booking.customer.last_name},",
        "",
        "Your MonkeyDo booking has been cancelled."
        if cancelled
        else "Your MonkeyDo visit was recorded as a no-show.",
        "Appointment: " + display_date(booking.session.starts_at, "l, F j, Y g:i A"),
        "",
    ]
    if checkout.sale:
        lines.append(f"Applicable fee total: ${checkout.sale.total:.2f}")
        if state["pending"]:
            lines.append(
                "Your card payment is pending confirmation; it has not yet been confirmed as received."
            )
        elif state["due"]:
            lines.append(f"Balance unpaid: ${state['due']:.2f}")
        else:
            lines.append("The applicable fee has been paid.")
    else:
        lines.append("No cancellation/no-show fee was charged.")
    if zelle["received"]:
        lines.append(f"Zelle previously received: ${zelle['received']:.2f}")
    if zelle["refund_due"]:
        lines.append(
            f"Zelle refund due: ${zelle['refund_due']:.2f}. The owner will return this manually; it has not yet been refunded."
        )
    lines += [
        "",
        "Please call or text us at 848-238-5147 if you need assistance.",
        "",
        "The MonkeyDo team",
    ]
    return enqueue(
        key="booking-closure:" + str(checkout.pk),
        kind="booking_cancelled" if cancelled else "booking_no_show",
        recipient=booking.customer.email,
        subject="Your MonkeyDo booking cancellation" if cancelled else "Your MonkeyDo visit update",
        text="\n".join(lines),
        customer=booking.customer,
        booking=booking,
        actor=actor,
    )
