"""One atomic renewal checkout applies backed credit without inventing receipts."""

import uuid
from datetime import date

from django.core.exceptions import ValidationError
from django.db import connection, transaction

from .membership_batch_credit_records import (
    MembershipCreditRenewalBatch,
    MembershipCreditRenewalPart,
)
from .membership_sales import authorize, offer, purchase, today
from .payments.amounts import ZERO, amount
from .payments.ledger import fingerprint, lock_request, writes_allowed


def available():
    if connection.vendor != "postgresql":
        return False
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT to_regclass('core_membershipcreditrenewalbatch') IS NOT NULL AND to_regclass('core_membershipcreditrenewalpart') IS NOT NULL AND to_regclass('core_membershipcreditrenewalmessage') IS NOT NULL AND to_regprocedure('monkeydo_credit_renewal_batch_backed()') IS NOT NULL"
        )
        return cursor.fetchone()[0]


def normalized_offer(data):
    from .membership_batch_renewals import normalized_offer as original_normalized

    result = original_normalized(data)
    # The parent confirms the complete initial pool. Each ordinary purchase
    # then records its actual current pool after earlier sibling applications.
    if result.get("credit"):
        result["credit"] = {"amount": result["credit"]["amount"]}
    return result


def purchase_values(*, actor, customer, line):
    selection = dict(line["selection"])
    selection.pop("method_id")
    return dict(
        actor=actor,
        customer=customer,
        **selection,
        starts_on=date.fromisoformat(line["offer"]["starts_on"]),
        expected_method="cash",
        operation="renewal",
        credit_amount=line["amount"],
    )


def review(*, actor, customer, rows):
    authorize(actor, collect=True)
    if not available():
        raise ValidationError("Complete the reviewed customer-credit renewal upgrade first.")
    from .customer_credit import available_issues
    from .membership_batch_renewals import packed
    from .membership_batch_renewals import review as ordinary_review
    from .models import Customer

    customer = Customer.objects.get(pk=customer.pk)
    base = ordinary_review(actor=actor, customer=customer, rows=rows, tender="cash")
    sources = [
        dict(id=str(source.pk), remaining=str(source.remaining))
        for source in available_issues(customer.pk)
    ]
    available_credit = sum((amount(source["remaining"]) for source in sources), ZERO)
    chosen = amount(base["amount"])
    if chosen > available_credit:
        raise ValidationError(
            f"These renewals need ${chosen:.2f} customer credit; ${available_credit:.2f} is currently available. Choose another payment method or adjust the selected renewals."
        )
    lines = []
    for line in base["lines"]:
        data = offer(**purchase_values(actor=actor, customer=customer, line=line))
        if amount(data["first_payment_total"]) or amount(
            data["installments"][0]["quote"]["processing_fee"]
        ):
            raise ValidationError("Review the full-credit funding before continuing.")
        lines.append(line | {"offer": packed(data)})
    facts = dict(
        actor=actor.pk,
        customer=customer.pk,
        customer_revision=customer.revision,
        contact=base["contact"],
        tender="credit",
        accepted_on=today().isoformat(),
        lines=lines,
        amount=str(chosen),
        sources=sources,
        available_before=str(available_credit),
        available_after=str(available_credit - chosen),
        new_money="0.00",
    )
    return facts | {"fingerprint": fingerprint(facts)}


@transaction.atomic
def confirm(*, actor, customer, rows, request_key, reviewed, accepted, credit_confirmed):
    authorize(actor, collect=True)
    writes_allowed()
    if not available():
        raise ValidationError("Complete the reviewed customer-credit renewal upgrade first.")
    from .membership_batch_records import MembershipRenewalBatch
    from .membership_batch_renewals import packed, queue_confirmation
    from .membership_reservations import lock_customer
    from .models import AuditEvent, Customer

    key = lock_request(request_key)
    old = MembershipCreditRenewalBatch.objects.filter(pk=key).first()
    if old:
        if (
            old.actor_id != actor.pk
            or old.customer_id != customer.pk
            or old.fingerprint != reviewed
        ):
            raise ValidationError("This checkout identity belongs to another reviewed renewal.")
        return old
    if MembershipRenewalBatch.objects.filter(pk=key).exists():
        raise ValidationError(
            "This checkout identity already records a received payment. Open that checkout."
        )
    if accepted is not True or credit_confirmed is not True:
        raise ValidationError(
            "Accept the current membership terms and authorize the customer credit shown."
        )
    customer = Customer.objects.select_for_update(no_key=True).get(pk=customer.pk)
    lock_customer(customer.pk)
    data = review(actor=actor, customer=customer, rows=rows)
    if data["fingerprint"] != reviewed:
        raise ValidationError(
            "The selected renewals, prices, customer or credit sources changed. Review again."
        )
    batch = MembershipCreditRenewalBatch.objects.create(
        id=key,
        customer=customer,
        actor=actor,
        fingerprint=reviewed,
        amount=amount(data["amount"]),
        facts=data | {"terms_accepted": True, "credit_confirmed": True},
    )
    for position, line in enumerate(data["lines"], 1):
        values = purchase_values(actor=actor, customer=customer, line=line)
        current = offer(**values)
        if normalized_offer(current) != normalized_offer(line["offer"]):
            raise ValidationError(
                "A renewal changed during checkout. No credit or renewal was saved."
            )
        part = MembershipCreditRenewalPart.objects.create(
            batch=batch,
            position=position,
            purchase_id=uuid.uuid5(key, f"renewal:{position}"),
            prior_id=line["selection"]["prior_id"],
            amount=amount(line["amount"]),
            facts=line,
            funding_offer=packed(current),
        )
        purchase(
            **values,
            request_key=part.purchase_id,
            reviewed=current["fingerprint"],
            accepted=True,
            verified_received=False,
            method_id=line["selection"]["method_id"],
        )
    queue_confirmation(batch)
    AuditEvent.objects.create(
        actor=actor,
        action="membership.renewals_credit_applied",
        record_type="membership_credit_renewal_batch",
        record_id=str(key),
        changes=dict(credit_applied=data["amount"], new_money="0.00", renewals=len(rows)),
    )
    return batch
