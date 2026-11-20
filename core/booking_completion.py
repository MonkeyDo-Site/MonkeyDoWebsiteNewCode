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
    booking.setup_pending = False
    booking.save(update_fields=["setup_pending"])


def confirmation(booking):
    from core.communications.content import booking_confirmation
    from core.communications.services import enqueue

    return enqueue(
        key=f"booking-confirmation:{booking.pk}",
        kind="booking_confirmation",
        recipient=booking.customer.email,
        subject="Your Monkey Do adventure is booked!",
        text=booking_confirmation(booking),
        customer=booking.customer,
        booking=booking,
    )
