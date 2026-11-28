"""Small durable DB queue. Leases never authorize repeating a financial POST."""

import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from .ledger import enabled
from .models import DurableJob, PaymentOperation


@transaction.atomic
def enqueue(*, kind, reference, key):
    if kind not in {
        "payment_dispatch",
        "payment_reconcile",
        "provider_event",
        "method_remove",
        "customer_email",
        "email_event",
        "membership_arrival",
        "membership_collection",
        "membership_paid_visit",
    }:
        raise ValidationError("Unsupported worker operation.")
    job, created = DurableJob.objects.get_or_create(
        key=key,
        defaults={"kind": kind, "reference": str(reference), "available_at": timezone.now()},
    )
    if not created and (job.kind != kind or job.reference != str(reference)):
        raise ValidationError("This worker key identifies a different operation.")
    return job


@transaction.atomic
def claim():
    now = timezone.now()
    eligible = DurableJob.objects.filter(
        Q(state="queued", available_at__lte=now) | Q(state="running", lease_until__lt=now)
    ).order_by("available_at", "created_at")
    eligible = (
        eligible.select_for_update(skip_locked=True)
        if connection.vendor == "postgresql"
        else eligible.select_for_update()
    )
    job = eligible.first()
    if job is None:
        return None
    if job.attempts >= 5:
        job.state = "blocked"
        job.code = "worker_attempt_limit"
        job.save(update_fields=["state", "code"])
        return None
    job.state = "running"
    job.lease_token = uuid.uuid4()
    job.lease_until = now + timedelta(minutes=2)
    job.attempts += 1
    job.save(update_fields=["state", "lease_token", "lease_until", "attempts"])
    return job


@transaction.atomic
def finish(job, state, code=""):
    return DurableJob.objects.filter(
        pk=job.pk, state="running", lease_token=job.lease_token
    ).update(state=state, code=code, lease_until=None)


def run_one():
    enabled()
    job = claim()
    if job is None:
        return False
    try:
        if job.kind == "provider_event":
            from .webhooks import process_event

            process_event(job.reference)
        elif job.kind == "email_event":
            from core.communications.webhooks import process_event

            process_event(job.reference)
        elif job.kind == "customer_email":
            from core.communications.services import deliver

            message = deliver(job.reference)
            if message.state in {"sending", "unknown", "failed", "queued"}:
                raise ValidationError("Email requires review before another attempt.")
        elif job.kind == "membership_collection":
            from core.membership_collection_queue import process

            process(job)
        elif job.kind == "membership_paid_visit":
            from core.membership_paid_visit_pending import complete

            complete(job.reference)
        elif job.kind == "membership_arrival":
            from core.membership_arrival_pending import complete

            complete(job.reference)
        elif job.kind == "method_remove":
            from .methods import remove_unused

            method = remove_unused(job.reference)
            if method.state != "removed":
                raise ValidationError("Card removal needs review.")
        else:
            from .ledger import record_result
            from .operations import execute, reconcile

            operation = PaymentOperation.objects.get(pk=job.reference)
            if job.kind == "payment_dispatch":
                if operation.state == "sending":
                    # A worker may have died after the provider received the POST.
                    record_result(
                        operation_id=operation.pk,
                        state="unknown",
                        source="worker",
                        code="interrupted_dispatch",
                    )
                    raise ValidationError("Interrupted payment requires reconciliation.")
                execute(operation.pk)
            elif job.kind == "payment_reconcile":
                reconcile(operation_id=operation.pk)
            else:
                raise ValidationError("Unsupported worker job.")
            operation.refresh_from_db()
            if operation.state in {"ready", "sending", "unknown", "action"}:
                raise ValidationError("Payment requires review before further action.")
        finish(job, "done")
    except Exception:
        # Persist a safe classification, never raw exception/provider bodies.
        # The worker does not retry the charge or send an automatic customer email.
        finish(job, "blocked", "review_required")
    return True
