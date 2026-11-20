"""Owner-reviewed queue recovery. Uncertain financial requests are never replayed."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.communications.models import MessageDelivery
from core.models import AuditEvent
from core.permissions import require_actor

from .methods import outstanding
from .models import DurableJob, PaymentMethod, PaymentOperation


def disposition(job):
    if job.state != "blocked":
        return None, "This background task is not blocked."
    if job.kind == "payment_dispatch":
        operation = PaymentOperation.objects.get(pk=job.reference)
        if operation.state == "ready":
            return (
                "resume",
                f"Send the original reviewed card operation for ${operation.amount:.2f}. No provider request has started.",
            )
        if operation.state in {"succeeded", "declined", "cancelled"}:
            return (
                "resolve",
                "The operation already has a recorded result. No provider request will be repeated.",
            )
        return (
            None,
            "Check and reconcile the original provider transaction. An uncertain charge/refund cannot be replayed.",
        )
    if job.kind in {"provider_event", "email_event", "payment_reconcile"}:
        return (
            "resume",
            "Resume read-only notification reconciliation. No financial POST will be sent.",
        )
    if job.kind == "customer_email":
        message = MessageDelivery.objects.get(pk=job.reference)
        if message.state == "queued":
            return (
                "resume",
                "Send the original queued message. Its sending request has not started.",
            )
        if message.state in {"sent", "delivered", "bounced", "failed", "cancelled"}:
            return "resolve", "Preserve the recorded message result and close this background task."
        return (
            None,
            "Check the message outcome before deliberately resending its booking confirmation. An uncertain send is not replayed.",
        )
    if job.kind == "method_remove":
        method = PaymentMethod.objects.get(pk=job.reference)
        if method.state == "removed":
            return "resolve", "Card removal is already confirmed."
        if method.state == "active" and not method.reusable and not outstanding(method):
            return "resume", "Remove this no-longer-needed booking card from the provider."
        return None, "Review the card’s outstanding bookings or provider removal result first."
    return None, "This task requires technical review."


@transaction.atomic
def recover(*, actor, job_id, action, confirmed):
    require_actor(actor, "core.review_payment", owner=True)
    if confirmed is not True:
        raise ValidationError("Confirm the reviewed recovery action.")
    job = DurableJob.objects.select_for_update().get(pk=job_id)
    expected, _ = disposition(job)
    if expected is None or expected != action:
        raise ValidationError("The recovery state changed. Review it again; nothing was replayed.")
    before = job.state
    if action == "resolve":
        job.state = "done"
    else:
        job.state, job.attempts, job.available_at = "queued", 0, timezone.now()
    job.lease_token = job.lease_until = None
    job.code = "owner_reviewed"
    job.save(
        update_fields=["state", "attempts", "available_at", "lease_token", "lease_until", "code"]
    )
    AuditEvent.objects.create(
        actor=actor,
        action="background.recovery_reviewed",
        record_type="background_job",
        record_id=str(job.pk),
        changes={"before": before, "after": job.state, "kind": job.kind},
    )
    return job
