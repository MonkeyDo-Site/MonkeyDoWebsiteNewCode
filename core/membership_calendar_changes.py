"""Current calendar views and explicit corrections of an unused paid/comped term."""

import uuid
from copy import copy
from datetime import date

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import DateField, F
from django.db.models.functions import Coalesce

from .membership_calendar import schedule
from .membership_calendar_records import MembershipCalendarCorrection, MembershipCalendarState
from .payments.ledger import fingerprint, lock_request, writes_allowed

ACKNOWLEDGMENT = "The customer confirmed the corrected membership dates shown."
OWNER_ACKNOWLEDGMENT = "As owner, I approve this exception. The customer agreed to the dates shown."


def owner_dates_available():
    if connection.vendor != "postgresql":
        return False
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regprocedure('monkeydo_calendar_owner_dates()') IS NOT NULL")
        return cursor.fetchone()[0]


def date_exception(actor, before, after):
    from .membership_sales import today
    from .permissions import require_actor

    needed = before < today() or after < today()
    if needed:
        if actor is not None and not actor.is_superuser:
            raise ValidationError("Only the owner can approve a membership date exception.")
        require_actor(actor, "core.change_membershipdraft", owner=True)
        if not owner_dates_available():
            raise ValidationError("Complete the reviewed owner date-exception upgrade first.")
    return needed


def available():
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
    return all(
        name in tables
        for name in ("core_membershipcalendarcorrection", "core_membershipcalendarstate")
    )


def with_calendar(records):
    """Annotate current search/filter dates without changing original contract fields."""
    if available():
        return records.annotate(
            calendar_starts_on=Coalesce(
                "calendar_state__correction__starts_on",
                F("membership__starts_on"),
                output_field=DateField(),
            ),
            calendar_ends_on=Coalesce(
                "calendar_state__correction__ends_on",
                F("membership__ends_on"),
                output_field=DateField(),
            ),
            calendar_cycles=F("calendar_state__correction__cycles"),
        )
    return records.annotate(
        calendar_starts_on=F("membership__starts_on"), calendar_ends_on=F("membership__ends_on")
    )


def current(member):
    original = member.membership
    if hasattr(member, "calendar_starts_on"):
        root = copy(original)
        root.starts_on, root.ends_on = member.calendar_starts_on, member.calendar_ends_on
        return root, getattr(member, "calendar_cycles", None)
    if not available():
        return original, None
    state = (
        MembershipCalendarState.objects.select_related("correction")
        .filter(purchase_id=member.pk)
        .first()
    )
    if state is None:
        return original, None
    root = copy(original)
    root.starts_on, root.ends_on = state.correction.starts_on, state.correction.ends_on
    return root, state.correction.cycles


def root_for(member):
    return current(member)[0]


def cycles_for(member):
    root, corrected = current(member)
    cycles = list(root.cycles.order_by("number"))
    if corrected:
        by_id = {row["id"]: row for row in corrected}
        for original in cycles:
            row = by_id.get(original.pk)
            if row is None:
                raise ValidationError(
                    "Review this membership's corrected calendar before continuing."
                )
            original.starts_on = date.fromisoformat(row["starts_on"])
            original.ends_on = date.fromisoformat(row["ends_on"])
    return cycles


def cycle_on(member, on):
    root, corrected = current(member)
    if not corrected:
        return root.cycles.filter(starts_on__lte=on, ends_on__gte=on).first()
    day = on.isoformat()
    row = next((row for row in corrected if row["starts_on"] <= day <= row["ends_on"]), None)
    if row is None:
        return None
    cycle = root.cycles.get(pk=row["id"])
    cycle.starts_on, cycle.ends_on = (
        date.fromisoformat(row["starts_on"]),
        date.fromisoformat(row["ends_on"]),
    )
    return cycle


def authorize(actor):
    from .membership_sales import enabled
    from .permissions import require_actor

    enabled()
    for permission in (
        "core.view_membershippurchase",
        "core.view_customer",
        "core.change_membershipdraft",
    ):
        require_actor(actor, permission)


def member_record(member_id):
    from .membership_records import MembershipPurchase

    return MembershipPurchase.objects.select_related("membership", "customer", "billing_state").get(
        pk=member_id
    )


def eligibility(member, *, actor=None):
    from .membership_funding import member_needs_review
    from .membership_sales import installment_paid, today

    root = root_for(member)
    if (
        member.billing_state.stopped_on
        or member.purpose not in {"purchase", "complimentary"}
        or member.confirmation_mode != "separate"
        or member.follow_on.exists()
        or member.benefit_assignments.exists()
        or hasattr(member, "origin")
    ):
        raise ValidationError(
            "Date corrections require a standalone prepaid or complimentary membership that has not been used in a booking. Review linked terms separately with the owner."
        )
    if root.starts_on < today():
        if not actor or not actor.is_superuser:
            raise ValidationError(
                "A term that has started or expired needs an explicit owner date exception."
            )
        date_exception(actor, root.starts_on, root.starts_on)
    if member.purpose != "complimentary":
        if root.billing != "prepaid":
            raise ValidationError(
                "Scheduled monthly dates need a separate payment-schedule review. This correction supports prepaid or complimentary terms."
            )
        installments = list(member.installments.select_related("invoice__sale"))
        if (
            len(installments) != 1
            or not installment_paid(installments[0])
            or member_needs_review(member)
        ):
            raise ValidationError(
                "Resolve the original membership payment before correcting its dates."
            )
        operations = installments[0].invoice.sale.operations.all()
        if (
            operations.exclude(kind="receipt").exists()
            or operations.filter(state__in=["ready", "sending", "unknown", "action"]).exists()
        ):
            raise ValidationError(
                "Review existing payment or refund outcomes before correcting dates."
            )
    return root


def review(*, actor, member_id, starts_on, reason="", send_confirmation=False):
    authorize(actor)
    if not available():
        raise ValidationError(
            "Complete the reviewed membership calendar upgrade before correcting dates."
        )
    if type(starts_on) is not date:
        raise ValidationError("Choose the corrected membership start date.")
    if not isinstance(reason, str) or len(reason) > 2000:
        raise ValidationError("Enter a correction reason, up to 2,000 characters.")
    if type(send_confirmation) is not bool:
        raise ValidationError("Choose whether to send an updated confirmation email.")
    member = member_record(member_id)
    root = eligibility(member, actor=actor)
    owner_exception = date_exception(actor, root.starts_on, starts_on)
    if starts_on == root.starts_on:
        raise ValidationError("The start date is unchanged.")
    before_cycles = cycles_for(member)
    dates = schedule(starts_on, root.months)
    state = (
        MembershipCalendarState.objects.select_related("correction").filter(purchase=member).first()
    )
    before = dict(
        starts_on=root.starts_on.isoformat(),
        ends_on=root.ends_on.isoformat(),
        cycles=[
            dict(
                id=row.pk,
                number=row.number,
                starts_on=row.starts_on.isoformat(),
                ends_on=row.ends_on.isoformat(),
            )
            for row in before_cycles
        ],
    )
    cycles = [
        dict(
            id=old.pk,
            number=new["number"],
            starts_on=new["starts_on"].isoformat(),
            ends_on=new["ends_on"].isoformat(),
        )
        for old, new in zip(before_cycles, dates, strict=True)
    ]
    data = dict(
        member=member.pk,
        customer=member.customer_id,
        customer_revision=member.customer.revision,
        actor=actor.pk,
        previous=str(state.correction_id) if state else None,
        version=state.correction.version + 1 if state else 1,
        before=before,
        starts_on=starts_on.isoformat(),
        ends_on=dates[-1]["ends_on"].isoformat(),
        cycles=cycles,
        reason=reason.strip(),
        months=root.months,
        places=root.places,
        kind=root.kind,
        billing=root.billing,
        unit_price=str(root.unit_price),
        billing_revision=member.billing_state.revision,
        customer_acknowledgment=ACKNOWLEDGMENT,
        send_confirmation=send_confirmation,
    )
    if owner_exception:
        data.update(owner_date_exception=True, owner_acknowledgment=OWNER_ACKNOWLEDGMENT)
    return data | {"fingerprint": fingerprint(data)}


@transaction.atomic
def confirm(
    *,
    actor,
    member_id,
    starts_on,
    reason,
    request_key,
    reviewed,
    customer_confirmed=False,
    send_confirmation=None,
    owner_approved=False,
):
    authorize(actor)
    writes_allowed()
    key = lock_request(request_key)
    old = MembershipCalendarCorrection.objects.filter(pk=key).first()
    if old:
        if old.purchase_id != member_id or old.actor_id != actor.pk or old.fingerprint != reviewed:
            raise ValidationError("This correction identity belongs to another reviewed change.")
        return old
    if customer_confirmed is not True or not isinstance(reason, str) or not reason.strip():
        raise ValidationError(
            "Record the reason and confirm that the customer agreed to the corrected dates."
        )
    if type(send_confirmation) is not bool:
        raise ValidationError("Choose whether to send an updated confirmation email.")
    from .membership_reservations import lock_customer
    from .models import AuditEvent, Customer

    member = member_record(member_id)
    Customer.objects.select_for_update(no_key=True).get(pk=member.customer_id)
    lock_customer(member.customer_id)
    data = review(
        actor=actor,
        member_id=member_id,
        starts_on=starts_on,
        reason=reason,
        send_confirmation=send_confirmation,
    )
    if data["fingerprint"] != reviewed:
        raise ValidationError("This membership changed. Review the corrected dates again.")
    if type(owner_approved) is not bool or owner_approved != data.get(
        "owner_date_exception", False
    ):
        raise ValidationError("Review and explicitly approve the owner date exception shown.")
    correction = MembershipCalendarCorrection.objects.create(
        id=key,
        purchase=member,
        previous_id=uuid.UUID(data["previous"]) if data["previous"] else None,
        version=data["version"],
        starts_on=starts_on,
        ends_on=date.fromisoformat(data["ends_on"]),
        before=data["before"],
        cycles=data["cycles"],
        facts=data,
        fingerprint=reviewed,
        reason=reason.strip(),
        customer_confirmed=True,
        send_confirmation=send_confirmation,
        actor=actor,
    )
    MembershipCalendarState.objects.update_or_create(
        purchase=member, defaults={"correction": correction}
    )
    AuditEvent.objects.create(
        actor=actor,
        action="membership.dates_corrected",
        record_type="membership",
        record_id=str(member.pk),
        changes=dict(
            before=data["before"],
            after=dict(starts_on=data["starts_on"], ends_on=data["ends_on"]),
            reason=reason.strip(),
            owner_date_exception=data.get("owner_date_exception", False),
        ),
    )
    from .membership_calendar_emails import queue, supersede

    supersede(member)
    queue(correction)
    return correction
