"""Atomic, explicitly received cash/check renewals with separate cohort history."""

import json
import uuid
from collections import Counter
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.db.models import Q

from .membership_batch_records import (
    MembershipRenewalBatch,
    MembershipRenewalBatchMessage,
    MembershipRenewalBatchPart,
)
from .membership_records import MembershipPurchase
from .membership_renewals import renewal_details
from .membership_sales import authorize, installment_paid, offer, purchase, today
from .payments.ledger import amount, fingerprint, lock_request, writes_allowed

ZERO = Decimal("0.00")
FIELDS = {"prior_id", "kind", "places", "months", "billing", "minimum_override", "method_id"}


def available():
    with connection.cursor() as cursor:
        return "core_membershiprenewalbatch" in connection.introspection.table_names(cursor)


def packed(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def review(*, actor, customer, rows, tender="cash"):
    authorize(actor, collect=True)
    if tender not in {"cash", "check"}:
        raise ValidationError("This combined renewal accepts verified cash or check only.")
    if not isinstance(rows, list) or not rows or len(rows) > 100:
        raise ValidationError("Choose between one and 100 renewal entries.")
    lines, counts, sources = [], Counter(), {}
    for row in rows:
        if not isinstance(row, dict) or set(row) - FIELDS:
            raise ValidationError("Review the selected membership renewal details.")
        prior_id = row.get("prior_id")
        if type(prior_id) is not int or prior_id <= 0:
            raise ValidationError("Choose an original membership to renew.")
        prior = sources.get(prior_id)
        if prior is None:
            prior = (
                MembershipPurchase.objects.select_related("membership", "billing_state")
                .filter(pk=prior_id, customer=customer)
                .first()
            )
            if prior is None:
                raise ValidationError("Choose memberships belonging to this customer.")
            sources[prior_id] = prior
        details = renewal_details(prior)
        selection = dict(
            prior_id=prior_id,
            kind=row.get("kind", prior.membership.kind),
            places=row.get("places", details["available_places"]),
            months=row.get("months", details["minimum_months"]),
            billing=row.get("billing", prior.membership.billing),
            minimum_override=row.get("minimum_override", False),
        )
        data = offer(
            actor=actor,
            customer=customer,
            **selection,
            starts_on=details["starts_on"],
            expected_method=tender,
            operation="renewal",
        )
        if amount(data["installments"][0]["quote"]["total"]) <= ZERO:
            raise ValidationError(
                "Each combined renewal needs a positive received payment. Use the individual renewal page when no payment is due."
            )
        counts[prior_id] += selection["places"]
        if counts[prior_id] > details["available_places"]:
            raise ValidationError(
                "The combined selection renews more places than this original membership has available."
            )
        method = row.get("method_id")
        if selection["billing"] == "monthly":
            mandate = prior.billing_state.mandate
            method = method or (str(mandate.method_id) if mandate else None)
            if not method:
                raise ValidationError(
                    "Choose a saved card for each monthly renewal's future installments."
                )
            try:
                method = str(uuid.UUID(str(method)))
            except (ValueError, TypeError, AttributeError):
                raise ValidationError("Choose a current saved membership card.") from None
            from .models import PaymentMethod

            allowed = Q(reusable=True)
            if mandate:
                allowed |= Q(pk=mandate.method_id)
            if not PaymentMethod.objects.filter(
                allowed,
                pk=method,
                customer=customer,
                state="active",
                environment="sandbox",
                provider_method__isnull=False,
            ).exists():
                raise ValidationError(
                    "Choose a current saved card for future membership installments."
                )
        elif method:
            raise ValidationError("A prepaid cash/check renewal does not need a card.")
        selection["method_id"] = method
        lines.append(
            dict(
                selection=selection,
                offer=packed(data),
                amount=data["installments"][0]["quote"]["total"],
            )
        )
    facts = dict(
        actor=actor.pk,
        customer=customer.pk,
        contact=dict(last_name=customer.last_name, phone=customer.phone, email=customer.email),
        tender=tender,
        received_on=today().isoformat(),
        lines=lines,
        amount=str(sum((amount(row["amount"]) for row in lines), ZERO)),
    )
    return facts | {"fingerprint": fingerprint(facts)}


def normalized_offer(data):
    result = packed(data)
    result.pop("fingerprint", None)
    result["origin"].pop("available_places", None)
    return result


@transaction.atomic
def confirm(*, actor, customer, rows, tender, request_key, reviewed, accepted, verified_received):
    authorize(actor, collect=True)
    writes_allowed()
    key = lock_request(request_key)
    existing = MembershipRenewalBatch.objects.filter(pk=key).first()
    if existing:
        if (
            existing.actor_id != actor.pk
            or existing.customer_id != customer.pk
            or existing.fingerprint != reviewed
        ):
            raise ValidationError(
                "This checkout identity already belongs to another reviewed renewal."
            )
        return existing
    if accepted is not True or verified_received is not True:
        raise ValidationError(
            "Accept the reviewed terms and confirm the full payment was actually received."
        )
    from .membership_reservations import lock_customer
    from .models import AuditEvent, Customer

    customer = Customer.objects.select_for_update(no_key=True).get(pk=customer.pk)
    lock_customer(customer.pk)
    data = review(actor=actor, customer=customer, rows=rows, tender=tender)
    if data["fingerprint"] != reviewed:
        raise ValidationError(
            "The selected memberships, prices or customer details changed. Review the combined renewal again."
        )
    batch = MembershipRenewalBatch.objects.create(
        id=key,
        customer=customer,
        actor=actor,
        fingerprint=reviewed,
        facts=data | {"terms_accepted": True, "verified_received": True},
        amount=amount(data["amount"]),
        tender=tender,
        received_on=date.fromisoformat(data["received_on"]),
    )
    for position, line in enumerate(data["lines"], 1):
        MembershipRenewalBatchPart.objects.create(
            batch=batch,
            position=position,
            purchase_id=uuid.uuid5(key, f"renewal:{position}"),
            prior_id=line["selection"]["prior_id"],
            amount=amount(line["amount"]),
            facts=line,
        )
    for part in batch.parts.order_by("position"):
        selection = dict(part.facts["selection"])
        method = selection.pop("method_id")
        values = dict(
            actor=actor,
            customer=customer,
            **selection,
            starts_on=date.fromisoformat(part.facts["offer"]["starts_on"]),
            expected_method=tender,
            operation="renewal",
        )
        current = offer(**values)
        if normalized_offer(current) != normalized_offer(part.facts["offer"]):
            raise ValidationError(
                "A renewal changed during checkout. No renewal or receipt was saved."
            )
        purchase(
            **values,
            request_key=part.purchase_id,
            reviewed=current["fingerprint"],
            accepted=True,
            verified_received=True,
            method_id=method,
        )
    queue_confirmation(batch)
    AuditEvent.objects.create(
        actor=actor,
        action="membership.renewals_received",
        record_type="membership_renewal_batch",
        record_id=str(key),
        changes=dict(amount=data["amount"], tender=tender, renewals=len(rows)),
    )
    return batch


def group_for(member):
    if not available():
        return None
    part = (
        MembershipRenewalBatchPart.objects.select_related("batch")
        .filter(purchase_id=member.request_key)
        .first()
    )
    return part.batch if part else None


def group_for_message(message):
    if not available():
        return None
    link = (
        MembershipRenewalBatchMessage.objects.select_related("batch")
        .filter(message=message)
        .first()
    )
    return link.batch if link else None


def cancel_messages(batch, code, *, exclude=None):
    from .communications.models import MessageEvent

    messages = batch.messages.select_related("message").filter(message__state="queued")
    if exclude:
        messages = messages.exclude(message_id=exclude)
    for link in messages:
        message = link.message
        message.state, message.code = "cancelled", code
        message.save(update_fields=["state", "code"])
        MessageEvent.objects.create(delivery=message, state="cancelled", code=code)


def queue_confirmation(batch):
    from django.conf import settings
    from django.urls import reverse

    from .communications.services import enqueue
    from .date_display import display_date
    from .membership_funding import member_needs_review

    if not settings.BOOKING_EMAIL_ENABLED:
        return None

    parts = list(
        batch.parts.select_related(
            "purchase__membership", "purchase__customer", "purchase__billing_state"
        ).order_by("position")
    )
    if len(parts) != len(batch.facts["lines"]):
        return None
    if any(
        part.purchase.cancellations.exists()
        or member_needs_review(part.purchase)
        or not installment_paid(
            part.purchase.installments.select_related("invoice__sale").order_by("number").first()
        )
        for part in parts
    ):
        cancel_messages(batch, "membership_batch_changed")
        return None
    customer = parts[0].purchase.customer
    if not customer.email:
        cancel_messages(batch, "contact_changed")
        return None
    key = f"membership-renewals:{batch.pk}:" + fingerprint(customer.email.casefold())
    old = batch.messages.select_related("message").filter(message__dedupe_key=key).first()
    if old:
        return (
            old.message if old.message.state in {"queued", "sending", "sent", "delivered"} else None
        )
    text = [
        f"Dear Family {customer.last_name},",
        "",
        "You're all set for more Monkey Do adventures!",
        "",
        "Your renewed memberships are ready:",
    ]
    for part in parts:
        root = part.purchase.membership
        text += [
            "",
            f"{root.places} {root.get_kind_display()} Membership"
            + ("s" if root.places != 1 else ""),
            f"Begins: {display_date(root.starts_on, 'F j, Y')}",
            f"Ends: {display_date(root.ends_on, 'F j, Y')}",
        ]
        next_item = part.purchase.installments.filter(number__gt=1).order_by("number").first()
        if next_item:
            text += [
                f"Your next scheduled membership payment is ${next_item.quote['total']} on {display_date(next_item.due_on, 'F j, Y')}."
            ]
    text += [
        "",
        f"Your payment of ${batch.amount:.2f} was received.",
        "Each membership keeps its own dates and benefits. The purchased terms end without automatic renewal.",
        "",
        "You can always renew your membership.",
        "",
        settings.BOOKING_STAGING_ORIGIN + reverse("schedule"),
        "",
        "Get ready to go bananas,",
        "The Monkey Do team",
    ]
    message = enqueue(
        key=key,
        kind="membership_renewal",
        recipient=customer.email,
        subject="Your Monkey Do memberships are renewed!",
        text="\n".join(text),
        customer=customer,
        membership=parts[0].purchase,
        actor=batch.actor,
    )
    MembershipRenewalBatchMessage.objects.create(batch=batch, message=message)
    cancel_messages(batch, "contact_changed", exclude=message.pk)
    return message
