"""Owner pauses only the visit to reconcile independently received visit funds."""

from django.core.exceptions import ValidationError
from django.db import transaction

from .membership_arrival_recovery import locked, require_owner
from .models import AuditEvent


def authorize(actor, intent, *, reviewing=False):
    require_owner(actor)
    if (
        intent.progress.status in {"completed", "stopped"}
        or intent.booking.attendance
        or intent.booking.workflow != "integrated_v1"
    ):
        raise ValidationError("This arrival has already ended. Open the saved booking.")
    # Visit-fund handling does not cancel or replace the conditional first card
    # request. Resolve an unstarted request explicitly on its own payment page.
    if intent.operation.state == "ready":
        raise ValidationError(
            "Review the existing membership payment before returning visit funds. It has not been sent."
        )
    if reviewing and (
        intent.progress.status != "review" or intent.progress.code != "owner_review_requested"
    ):
        raise ValidationError("Start an owner review of unused visit funds from the arrival page.")


@transaction.atomic
def pause(*, actor, intent_id):
    from .membership_arrival_pending import mark_review
    from .membership_arrival_receipts import held

    require_owner(actor)
    intent = locked(intent_id)
    authorize(actor, intent)
    if not held(intent):
        raise ValidationError("There are no unused visit funds to return for this arrival.")
    if intent.progress.code == "owner_review_requested":
        return intent.progress
    state = mark_review(intent, "owner_review_requested")
    AuditEvent.objects.create(
        actor=actor,
        action="membership.arrival_funds_review_started",
        record_type="booking",
        record_id=str(intent.booking.reference),
        changes={"intent_id": str(intent.pk)},
    )
    return state
