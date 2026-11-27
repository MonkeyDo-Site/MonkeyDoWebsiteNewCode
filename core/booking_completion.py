"""Independent opt-in boundary for the completed sandbox booking workflow."""

from django.conf import settings
from django.core.exceptions import ValidationError


def enabled():
    if (
        settings.RECOVERY_HOLD
        or not settings.BOOKING_COMPLETION_ENABLED
        or not all(
            (
                settings.PAYMENT_SANDBOX_ENABLED,
                settings.WAIVER_ENABLED,
                settings.BOOKING_EMAIL_ENABLED,
            )
        )
        or settings.APP_ENV not in {"test", "development", "staging"}
    ):
        raise ValidationError("The completed sandbox booking workflow is not enabled.")


def integrated(flow):
    return flow.get("workflow") == "integrated_v1"


def complete(flow, booking):
    from core.payments.setup import bind_booking as bind_card
    from core.waivers.services import bind_booking as bind_waivers

    enabled()
    bind_card(flow=flow, booking=booking)
    bind_waivers(flow=flow, booking=booking)
    from .membership_booking import confirm as confirm_membership

    confirm_membership(booking, actor=None)
    booking.setup_pending = False
    booking.save(update_fields=["setup_pending"])


def confirmation(booking, *, flow=None):
    from core.communications.content import booking_confirmation, session_subject
    from core.communications.services import enqueue

    payload = confirmation_payload(booking, flow=flow)
    return enqueue(
        key=f"booking-confirmation:{booking.pk}",
        kind=payload["kind"],
        recipient=booking.customer.email,
        subject=session_subject(booking),
        text=booking_confirmation(
            booking, waiver_url=payload["waiver_url"], waiver_type=payload["waiver_type"]
        ),
        unsigned_waiver=payload["unsigned_waiver"],
        customer=booking.customer,
        booking=booking,
    )


def confirmation_payload(booking, *, flow=None, actor=None):
    from django.urls import reverse

    from core.waivers.models import BookingWaiverReview
    from core.waivers.services import create_share

    review = BookingWaiverReview.objects.filter(booking=booking).first()
    shared = bool(review and review.share_requested)
    url = None
    if shared:
        _, token = create_share(actor=actor, booking_id=booking.pk, flow=flow)
        url = settings.BOOKING_STAGING_ORIGIN + reverse("shared_waiver", args=[token])
    return {
        "kind": "booking_waiver" if shared else "booking_confirmation",
        "waiver_url": url,
        "waiver_type": "online_shared" if shared else "single",
        "unsigned_waiver": shared,
    }
