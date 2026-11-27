"""Explicit arrival redemption of existing funds, never a new cash receipt."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError

from .customer_credit import available_issues
from .customer_credit_records import CustomerCreditAllocation, CustomerCreditApplication
from .models import AuditEvent
from .payments.amounts import COMPONENTS, ZERO, allocate, amount
from .payments.ledger import fingerprint
from .pricing import quote_lines


def configure(form, booking, actor):
    if (
        not settings.MEMBERSHIP_SALES_ENABLED
        or actor is None
        or not actor.has_perm("core.collect_payment")
    ):
        return
    from django import forms

    from .customer_credit import balance, held_balance

    available = balance(booking.customer_id)
    form.visit_credit_available = available
    form.visit_credit_held = held_balance(booking.customer_id)
    values = form.data if form.is_bound else form.initial
    if available or values.get("visit_credit"):
        purchase_tip = (
            " For a new membership purchase, use its credit field above."
            if "member_add" in form.fields
            else ""
        )
        form.fields["visit_credit"] = forms.DecimalField(
            required=False,
            min_value=ZERO,
            max_digits=14,
            decimal_places=2,
            initial=ZERO,
            label="Existing customer credit to apply",
            help_text=f"Available: ${available:.2f}. Credit is separate from new money received."
            + purchase_tip,
        )


def verify_receipts(data, plan):
    for tender, field, message in (
        ("gift_card", "gift_card_verified", "Present and verify the physical gift card."),
        ("zelle", "zelle_verified", "Verify the new Zelle receipt in the business bank account."),
    ):
        if (
            any(
                part["tender"] == tender and not part.get("advance") and amount(part["amount"])
                for part in plan
            )
            and data.get(field) is not True
        ):
            raise ValidationError(message)


def confirm_label(plan):
    value = sum((amount(part["amount"]) for part in plan if part["tender"] == "credit"), ZERO)
    if not value:
        return None
    actions = [f"apply ${value:.2f} credit"]
    for part in plan:
        if part["tender"] == "credit" or not amount(part["amount"]):
            continue
        label = "gift card" if part["tender"] == "gift_card" else part["tender"]
        actions.append(
            f"apply recorded Zelle ${part['amount']}"
            if part.get("advance")
            else f"charge card ${part['amount']}"
            if label == "card"
            else f"record {label} ${part['amount']}"
        )
    return "Confirm arrival — " + " and ".join(actions)


def review(*, booking, policy, lines, value, kind, comped=False, combined=False):
    chosen = amount(value or ZERO)
    if not chosen:
        return None
    if not settings.MEMBERSHIP_SALES_ENABLED or kind != "arrival":
        raise ValidationError("Customer credit is available for reviewed arrivals only.")
    if comped:
        raise ValidationError("No customer credit is needed for an owner-comped visit.")
    if combined:
        raise ValidationError(
            "Apply credit to the membership purchase above, or redeem visit credit without a new membership purchase. Combined credit allocation still needs its separate review."
        )
    if any(
        line.label in {"Partial cancellation fee", "Cancellation fee"} and line.quantity
        for line in lines
    ):
        raise ValidationError(
            "This visit includes a cancellation fee. Review that fee separately before applying admission credit. No credit was spent."
        )
    from .payments.zelle import facts

    gross = amount(quote_lines(lines, policy, card_base=ZERO)["total"])
    remaining = max(ZERO, gross - facts(booking)["available"])
    sources = available_issues(booking.customer_id)
    available = sum((source.remaining for source in sources), ZERO)
    if chosen > min(available, remaining):
        raise ValidationError(
            f"Apply credit within the ${available:.2f} available balance and ${remaining:.2f} visit balance after recorded Zelle."
        )
    return {
        "amount": str(chosen),
        "available": str(available),
        "sources": [
            {"id": str(source.pk), "remaining": str(source.remaining)} for source in sources
        ],
    }


def apply(*, actor, checkout, plan, part):
    """Caller holds booking/customer locks inside its final atomic confirmation."""
    from .membership_reservations import lock_customer

    lock_customer(checkout.booking.customer_id)
    key = uuid.uuid5(checkout.request_key, "visit-customer-credit")
    prior = CustomerCreditApplication.objects.filter(pk=key).first()
    if prior:
        if prior.booking_checkout_id != checkout.pk or prior.actor_id != actor.pk:
            raise ValidationError("This credit confirmation belongs to another arrival.")
        return prior
    sources = available_issues(checkout.booking.customer_id)
    if plan["sources"] != [
        {"id": str(source.pk), "remaining": str(source.remaining)} for source in sources
    ]:
        raise ValidationError("The available credit changed. Review the visit again.")
    details = {"checkout": str(checkout.pk), "booking": checkout.booking_id, **plan}
    record = CustomerCreditApplication.objects.create(
        id=key,
        booking_checkout=checkout,
        customer_id=checkout.booking.customer_id,
        sale=checkout.sale,
        amount=amount(plan["amount"]),
        fingerprint=fingerprint(details),
        details=details,
        actor=actor,
    )
    lines = list(checkout.sale.lines.all())
    if len(lines) != len(part["parts"]):
        raise ValidationError("The credit allocation does not match the accepted visit lines.")
    remaining = [
        {component: amount(row[component]) for component in COMPONENTS} for row in part["parts"]
    ]
    left = record.amount
    for source in sources:
        used = min(left, source.remaining)
        if not used:
            continue
        portions = allocate(used, [row[component] for row in remaining for component in COMPONENTS])
        allocation = [
            {
                "line": str(line.pk),
                **{
                    component: str(portions[i * len(COMPONENTS) + j])
                    for j, component in enumerate(COMPONENTS)
                },
            }
            for i, line in enumerate(lines)
        ]
        CustomerCreditAllocation.objects.create(
            application=record, issue=source, amount=used, allocation=allocation
        )
        for i, row in enumerate(remaining):
            for j, component in enumerate(COMPONENTS):
                row[component] -= portions[i * len(COMPONENTS) + j]
        left -= used
        if not left:
            break
    if left or any(value for row in remaining for value in row.values()):
        raise ValidationError("Credit changed; no arrival or application was recorded.")
    AuditEvent.objects.create(
        actor=actor,
        action="customer.credit_applied",
        record_type="booking",
        record_id=str(checkout.booking.reference),
        changes={
            "application": str(record.pk),
            "amount": str(record.amount),
            "checkout": str(checkout.pk),
        },
    )
    return record
