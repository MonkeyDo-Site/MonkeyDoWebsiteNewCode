"""Bounded daily preparation; no catch-up dates, repeated attempts or provider I/O."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import CharField, Exists, F, OuterRef, Q, Value
from django.db.models.functions import Cast, Concat

from .availability import NEW_YORK
from .membership_collection_authority import enabled
from .membership_collection_plan import installment_plan
from .membership_collections import schedule_installment
from .membership_records import MembershipInstallment
from .membership_sales import installment_paid, today
from .models import DurableJob
from .payments.jobs import enqueue
from .payments.ledger import lock_request

KIND = "membership_collection"
PREFIX = "membership-collection:"


def key(installment_id):
    if type(installment_id) is not int or installment_id <= 0:
        raise ValidationError("Use a current installment for scheduled preparation.")
    return PREFIX + str(installment_id)


@transaction.atomic
def prepare_job(installment_id):
    identity = key(installment_id)
    lock_request(uuid.uuid5(uuid.NAMESPACE_URL, "monkeydo:" + identity))
    existing = DurableJob.objects.filter(key=identity).first()
    if existing:
        if existing.kind != KIND or existing.reference != str(installment_id):
            raise ValidationError("The scheduled preparation identity needs review.")
        return existing, False
    return enqueue(kind=KIND, reference=installment_id, key=identity), True


def prepare_due(*, limit=20):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValidationError("Use a scheduling batch between 1 and 100.")
    if not settings.MEMBERSHIP_SALES_ENABLED or not settings.MEMBERSHIP_COLLECTIONS_ENABLED:
        return {"enabled": False, "queued": 0, "jobs": []}
    enabled()
    existing = DurableJob.objects.filter(
        key=Concat(Value(PREFIX), Cast(OuterRef("pk"), CharField()))
    )
    candidates = (
        MembershipInstallment.objects.filter(
            number__gt=1,
            due_on=today(),
            purchase__membership__billing="monthly",
            invoice__isnull=True,
            collection_claim__isnull=True,
        )
        .exclude(purchase__purpose="complimentary")
        .exclude(
            Q(purchase__billing_state__stopped_on__isnull=False)
            & Q(cycle__starts_on__gte=F("purchase__billing_state__stopped_on"))
        )
        .annotate(prepared=Exists(existing))
        .filter(prepared=False)
        .order_by("purchase_id", "number")
    )
    jobs, created = [], 0
    for pk in candidates.values_list("pk", flat=True)[:limit]:
        job, is_new = prepare_job(pk)
        jobs.append(str(job.pk))
        created += is_new
    return {"enabled": True, "queued": created, "jobs": jobs}


def installment_for(job):
    try:
        pk = int(job.reference)
    except (ValueError, TypeError):
        raise ValidationError("The scheduled preparation reference needs review.") from None
    item = MembershipInstallment.objects.select_related(
        "purchase__customer", "purchase__membership", "invoice__sale"
    ).get(pk=pk)
    if (
        job.kind != KIND
        or job.key != key(pk)
        or job.reference != str(pk)
        or job.created_at.astimezone(NEW_YORK).date() != item.due_on
    ):
        raise ValidationError("The scheduled preparation identity needs review.")
    return item


def process(job):
    enabled()
    item = installment_for(job)
    if item.due_on != today():
        raise ValidationError(
            "Use explicit membership payment controls for a missed scheduled date."
        )
    return schedule_installment(item.pk)


def disposition(job):
    try:
        item = installment_for(job)
    except (ValidationError, MembershipInstallment.DoesNotExist):
        return (
            None,
            "This scheduled preparation needs technical review. No new payment was requested.",
        )
    if hasattr(item, "invoice"):
        if item.invoice.sale.operations.filter(state__in=["sending", "unknown", "action"]).exists():
            return (
                None,
                "Check the existing payment outcome in the membership before continuing. An uncertain charge cannot be repeated.",
            )
        if installment_paid(item):
            return (
                "resolve",
                "This installment is already funded. Close the preparation task without applying credit or requesting payment again.",
            )
        return (
            "resolve",
            "This installment already has a payment review. Use its membership payment controls for resolution. Closing this task does not mark it paid.",
        )
    if item.due_on < today():
        return (
            "resolve",
            "This installment's scheduled date has passed. Use the membership payment controls for an explicit collection. Closing this task does not record payment.",
        )
    if not settings.MEMBERSHIP_COLLECTIONS_ENABLED:
        return (
            None,
            "Scheduled collection is paused. The membership payment controls remain available.",
        )
    data = installment_plan(item.pk)
    if data["status"] != "ready_for_scheduling":
        return None, " ".join(
            data["messages"]
        ) + " Review the membership before resuming this task."
    if data["card_total"] == "0.00":
        return "resume", (
            "Resume preparation under the accepted installment terms. Current estimate: $"
            + data["credit_to_apply"]
            + " existing credit. No card charge will be requested."
        )
    return "resume", (
        "Resume preparation under the accepted installment terms. Current estimate: $"
        + data["credit_to_apply"]
        + " existing credit and $"
        + data["card_total"]
        + " on the accepted card. No charge has been requested yet."
    )
