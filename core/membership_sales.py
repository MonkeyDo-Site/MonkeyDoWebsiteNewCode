"""Explicit accepted purchases. Quotes never activate benefits or collect funds."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .availability import NEW_YORK
from .membership_calendar import schedule
from .membership_records import (
    MembershipBilling,
    MembershipCardMandate,
    MembershipInstallment,
    MembershipInvoice,
    MembershipOrigin,
    MembershipPurchase,
)
from .membership_terms import VERSION, rules_snapshot, terms
from .models import (
    AuditEvent,
    Customer,
    MembershipDraft,
    MembershipDraftCycle,
    MembershipPricing,
    PricingPolicy,
)
from .payments.amounts import ZERO, amount
from .payments.invoices import received, settled, total
from .payments.ledger import (
    fingerprint,
    full_allocation,
    lock_request,
    record_manual,
    request_operation,
    writes_allowed,
)
from .payments.models import FinancialLine, FinancialSale, PaymentMethod
from .permissions import require_actor
from .pricing import Line, quote_lines


def enabled():
    from .booking_completion import enabled as booking_enabled

    booking_enabled()
    if not settings.MEMBERSHIP_SALES_ENABLED:
        raise ValidationError("Active membership sales are not enabled.")


def authorize(actor, *, collect=False, authority=None):
    enabled()
    if actor is None and authority:
        from .membership_public_authority import verified_scope

        verified_scope(authority)
        return
    for permission in (
        "core.view_customer",
        "core.view_membershippurchase",
        "core.add_membershippurchase",
    ):
        require_actor(actor, permission)
    if collect:
        require_actor(actor, "core.collect_payment")


def today():
    return timezone.localdate(timezone=NEW_YORK)


def offer(
    *,
    actor,
    customer,
    kind,
    places,
    months,
    billing,
    starts_on,
    expected_method,
    minimum_override=False,
    comped=False,
    operation="purchase",
    prior_id=None,
    authority=None,
    credit_amount=ZERO,
    split=None,
    split_sender="",
    split_received_on=None,
    bank_booking_id=None,
    bank_amount=ZERO,
    paid_visit_id=None,
):
    authorize(actor, authority=authority)
    if actor is None:
        from .membership_public_authority import check_selection

        check_selection(
            authority,
            customer_id=customer.pk,
            operation=operation,
            prior_id=prior_id,
            tender=expected_method,
        )
    if any(type(value) is not bool for value in (minimum_override, comped)):
        raise ValidationError("Review the owner exception choices.")
    if minimum_override or comped:
        require_actor(actor, "core.add_membershippurchase", owner=True)
    if kind not in {"subscription", "unlimited"} or billing not in {"monthly", "prepaid"}:
        raise ValidationError("Choose a supported membership and billing option.")
    if type(places) is not int or not 1 <= places <= 2147483647:
        raise ValidationError("Enter a positive whole number of membership places.")
    if operation not in {"purchase", "renewal", "addition"}:
        raise ValidationError("Choose a purchase, renewal or additional membership places.")
    minimum = 3
    origin = None
    if operation != "purchase":
        from .membership_renewals import effective_expiry, renewal_details

        if type(prior_id) is not int or prior_id <= 0:
            raise ValidationError("Choose the original membership for this purchase.")
        prior = (
            MembershipPurchase.objects.select_related("membership", "billing_state")
            .filter(pk=prior_id, customer=customer)
            .first()
        )
        if prior is None:
            raise ValidationError(
                "This original membership belongs to another customer or is unavailable."
            )
        expiry = effective_expiry(prior)
        origin = {
            "prior_id": prior.pk,
            "prior_ends_on": expiry.isoformat(),
            "purchased_on": today().isoformat(),
        }
        if operation == "renewal":
            details = renewal_details(prior)
            minimum = details["minimum_months"]
            if starts_on != details["starts_on"]:
                raise ValidationError(
                    "Renewal begins after the current term, or on the purchase date when renewing after expiry. Review the start date."
                )
            if places > details["available_places"]:
                raise ValidationError(
                    "These membership places already have a renewal. Open that renewal or choose fewer places; new additional places require their own purchase."
                )
            origin["available_places"] = details["available_places"]
        origin["minimum_months"] = minimum
    elif prior_id is not None:
        raise ValidationError(
            "Use the renewal or additional-place action to link an original membership."
        )
    if type(months) is not int or months < (1 if minimum_override or comped else minimum):
        raise ValidationError(
            "New memberships require at least three months unless the owner approves an exception."
        )
    if type(starts_on) is not date or starts_on < today():
        raise ValidationError("Choose today or a future membership start date.")
    if expected_method not in {"card", "cash", "check", "zelle", "gift_card", "split"}:
        raise ValidationError("Choose a supported membership payment method.")
    if split and expected_method != "split":
        raise ValidationError("Choose split payment before entering separate received amounts.")
    from .membership_bank import review as review_bank

    if amount(bank_amount) and (expected_method != "split" or operation != "purchase"):
        raise ValidationError(
            "Apply recorded booking Zelle through the combined first-payment split."
        )
    bank = review_bank(
        actor=actor, customer=customer, booking_id=bank_booking_id, value=bank_amount, comped=comped
    )
    from .membership_initial_credit import review as review_credit

    credit = review_credit(actor=actor, customer=customer, value=credit_amount, comped=comped)
    pricing, policy = MembershipPricing.objects.first(), PricingPolicy.objects.first()
    if not pricing or not policy:
        raise ValidationError("Membership pricing is unavailable.")
    rows = schedule(starts_on, months)
    unit = Decimal("0.00") if comped else getattr(pricing, kind)
    installments = []
    for row in rows:
        due = billing == "monthly" or row["number"] == 1
        if not due or comped:
            continue
        tender = expected_method if row["number"] == 1 else "card"
        principal = unit * places * (months if billing == "prepaid" else 1)
        applied_credit = amount(credit["amount"]) if credit and row["number"] == 1 else ZERO
        if applied_credit > principal:
            raise ValidationError("Apply credit only within the initial membership principal.")
        first_plan = None
        if tender == "split":
            from .membership_first_split import review as split_review

            first_plan = split_review(
                principal=principal,
                credit=applied_credit,
                split=split or {},
                policy=policy,
                sender_name=split_sender,
                received_on=split_received_on,
                recorded=bank,
            )
        quote = quote_lines(
            [
                Line(
                    f"{kind.title()} Membership",
                    places,
                    unit * (months if billing == "prepaid" else 1),
                    False,
                )
            ],
            policy,
            card_base=amount(first_plan["card_net"])
            if first_plan
            else (principal - applied_credit)
            if tender == "card"
            else ZERO,
        )
        if first_plan:
            quote["initial_split"] = first_plan
        if amount(quote["total"]) > Decimal("20000000.00"):
            raise ValidationError(
                "The installment exceeds the supported payment amount. Review places and billing."
            )
        installments.append(
            {
                "number": row["number"],
                "due_on": (today() if row["number"] == 1 else row["charge_on"]).isoformat(),
                "quote": quote,
            }
        )
    data = {
        "customer_id": customer.pk,
        "customer_revision": customer.revision,
        "kind": kind,
        "places": places,
        "months": months,
        "billing": billing,
        "starts_on": starts_on.isoformat(),
        "ends_on": rows[-1]["ends_on"].isoformat(),
        "unit_price": str(unit),
        "pricing_id": pricing.pk,
        "policy_id": policy.pk,
        "comped": comped,
        "minimum_override": minimum_override,
        "expected_method": expected_method,
        "operation": operation,
        "origin": origin,
        "minimum_months": minimum,
        "installments": installments,
        "rules": rules_snapshot(),
        "terms_version": VERSION,
        "terms": terms(
            kind=kind,
            starts_on=starts_on,
            months=months,
            billing=billing,
            minimum_override=minimum_override,
            comped=comped,
            renewal=operation == "renewal",
            minimum_months=minimum,
        ),
    }
    if installments:
        first = installments[0]
        if first["quote"].get("initial_split"):
            data["first_payment_plan"] = first["quote"]["initial_split"]
            data["first_payment_total"] = str(
                amount(first["quote"]["total"])
                - amount(data["first_payment_plan"]["credit_amount"])
            )
        if credit:
            data["credit"] = credit
            data["first_payment_total"] = str(
                amount(first["quote"]["total"]) - amount(credit["amount"])
            )
        if bank:
            data["first_payment_total"] = str(
                amount(data["first_payment_total"]) - amount(bank["amount"])
            )
            data["terms"] += (
                f" Previously recorded booking Zelle of ${bank['amount']} is applied to this first membership payment."
            )
        if data.get("first_payment_plan"):
            labels = {
                "cash": "cash",
                "check": "check",
                "zelle": "verified Zelle",
                "gift_card": "verified physical gift card",
                "card": "card",
            }
            data["terms"] += (
                " The first payment is split as follows: "
                + ", ".join(
                    f"${part['amount']} {labels[part['tender']]}"
                    for part in data["first_payment_plan"]["parts"]
                )
                + "."
            )
        data["terms"] += (
            f" The accepted price is ${unit:.2f} per place per month for {places} place(s)."
            f" The first payment due today is ${data.get('first_payment_total', first['quote']['total'])}, including a card processing fee of ${first['quote']['processing_fee']}. Membership and membership processing fees are not subject to sales tax."
        )
        if credit:
            data["terms"] += (
                f" Existing customer credit of ${credit['amount']} is applied to this purchase. This is not a new receipt. Only the remaining payment is collected today."
            )
        if billing == "monthly":
            data["terms"] += (
                f" The remaining {months - 1} monthly installments use the accepted saved card."
                f" Each is ${installments[1]['quote']['total'] if len(installments) > 1 else first['quote']['total']}, including the accepted card processing fee."
                " Charge dates follow the original membership start day; if that day is absent, the charge falls on the month's last day and the benefits reset the following day."
                if months > 1
                else " There are no further installments in this term."
            )
    if paid_visit_id is not None:
        from .membership_paid_visit import prepare_offer

        if bank:
            raise ValidationError(
                "Keep unapplied booking Zelle separate from an already-paid visit conversion."
            )
        data = prepare_offer(
            actor=actor,
            booking_id=paid_visit_id,
            data=data | {"cycles": rows},
            credit_amount=credit_amount,
        )
        data.pop("cycles")
    return data | {"fingerprint": fingerprint(data), "cycles": rows}


@transaction.atomic
def purchase(
    *,
    actor,
    request_key,
    reviewed,
    accepted,
    method_id=None,
    card_authorization_id=None,
    send_confirmation=None,
    verified_received=False,
    received_on=None,
    gift_card_verified=False,
    zelle_verified=False,
    authority=None,
    combined_booking=None,
    **values,
):
    authorize(actor, collect=True, authority=authority)
    writes_allowed()
    key = lock_request(request_key)
    if actor is None:
        from .membership_public_authority import verified_scope

        if key != verified_scope(authority)["request_key"]:
            raise PermissionDenied
    prior = MembershipPurchase.objects.select_related("membership").filter(request_key=key).first()
    if prior:
        if prior.actor_id != (actor.pk if actor else None) or prior.fingerprint != reviewed:
            raise ValidationError(
                "This membership request has already been used. Open the saved membership."
            )
        if actor is None:
            from .membership_public_authority import check_purchase

            check_purchase(authority, prior)
        return prior
    if accepted is not True:
        raise ValidationError("Review and accept the membership terms before confirming.")
    if values.get("paid_visit_id") is not None:
        from .calendar import lock_calendar
        from .models import Booking, Session

        if combined_booking is not None:
            raise ValidationError(
                "Keep this already-paid visit conversion separate from a new arrival."
            )
        if type(values["paid_visit_id"]) is not int or values["paid_visit_id"] <= 0:
            raise ValidationError("Choose a valid paid visit for this purchase.")
        lock_calendar()
        visit = (
            Booking.objects.select_for_update()
            .filter(pk=values["paid_visit_id"], customer_id=values["customer"].pk)
            .first()
        )
        if visit is None:
            raise ValidationError("Choose this customer's paid visit for this purchase.")
        Session.objects.select_for_update().get(pk=visit.session_id)
    # Protect identity/contact updates while allowing customer FK checks from
    # an already-locked credit correction to finish before our advisory lock.
    customer = Customer.objects.select_for_update(no_key=True).get(pk=values["customer"].pk)
    from .membership_reservations import lock_customer

    lock_customer(customer.pk)
    if actor is None:
        from .membership_public_authority import acceptance_filter, verified_scope
        from .membership_records import MembershipPublicAcceptance

        scope = verified_scope(authority)
        if (
            not card_authorization_id
            or MembershipPublicAcceptance.objects.filter(**acceptance_filter(scope)).exists()
        ):
            raise ValidationError(
                "This membership needs its current card authorization, or already has a purchase recorded."
            )
    values["customer"] = customer
    if combined_booking is not None:
        from .payments.checkout import authorize as authorize_arrival

        authorize_arrival(actor)
        if combined_booking.customer_id != customer.pk or authority is not None:
            raise ValidationError("Use this customer's staff arrival to combine the purchase.")
    data = offer(actor=actor, authority=authority, **values)
    if data["fingerprint"] != reviewed:
        raise ValidationError(
            "The membership or price changed. Review the current total and confirm again."
        )
    if data["comped"] and type(send_confirmation) is not bool:
        raise ValidationError(
            "Choose Yes or No for sending the complimentary membership confirmation."
        )
    method = None
    due_now = (
        amount(data.get("first_payment_total", data["installments"][0]["quote"]["total"]))
        if data["installments"]
        else ZERO
    )
    needs_card = card_required(data)
    if needs_card:
        available = Q(reusable=True)
        if card_authorization_id:
            from .membership_card_setup import reviewed_source

            authorized_method = reviewed_source(
                actor=actor,
                authorization_id=card_authorization_id,
                customer=customer,
                request_key=key,
                reviewed=reviewed,
            )
            if str(authorized_method.pk) != str(method_id):
                raise ValidationError("Use the card authorized for this membership purchase.")
            available |= Q(pk=authorized_method.pk)
        if data["origin"]:
            old = MembershipPurchase.objects.get(
                pk=data["origin"]["prior_id"]
            ).billing_state.mandate
            if old:
                available |= Q(pk=old.method_id)
        method = (
            PaymentMethod.objects.select_for_update()
            .filter(available)
            .filter(
                pk=method_id,
                customer=customer,
                state="active",
                environment="sandbox",
            )
            .exclude(provider_method__isnull=True)
            .first()
        )
        if not method:
            raise ValidationError(
                "Choose a current saved card for the membership payment and scheduled installments."
            )
    elif method_id:
        raise ValidationError("No card is needed for this selected membership payment.")
    if data.get("first_payment_plan"):
        from .membership_first_split import verify

        verify(
            data["first_payment_plan"],
            verified_received=verified_received,
            gift_card_verified=gift_card_verified,
            zelle_verified=zelle_verified,
        )
    elif due_now > ZERO and data["expected_method"] != "card" and verified_received is not True:
        raise ValidationError("Confirm that the membership payment was actually received.")
    root = MembershipDraft.objects.create(
        customer=customer,
        kind=data["kind"],
        places=data["places"],
        months=data["months"],
        billing=data["billing"],
        starts_on=values["starts_on"],
        ends_on=date.fromisoformat(data["ends_on"]),
        unit_price=amount(data["unit_price"]),
        pricing_id=data["pricing_id"],
        fee_policy_id=data["policy_id"],
        expected_method=data["expected_method"],
        creation_key=key,
        actor=actor,
        snapshot={
            "status": "purchase",
            "test_mode": True,
            "original_anchor_day": values["starts_on"].day,
            "terms_accepted": True,
            "monthly_subtotal": str(amount(data["unit_price"]) * data["places"]),
            "term_subtotal": str(amount(data["unit_price"]) * data["places"] * data["months"]),
            **(
                {
                    "paid_visit_purchase": {
                        "booking": data["paid_visit"]["booking"],
                        "applied": data["paid_visit"]["applied"],
                        "new_payment": data["paid_visit"]["new_payment"],
                    }
                }
                if data.get("paid_visit")
                else {}
            ),
        },
    )
    row_by_number = {row["number"]: row for row in data["installments"]}
    cycles = []
    for row in data["cycles"]:
        installment = row_by_number.get(row["number"])
        cycles.append(
            MembershipDraftCycle(
                draft=root,
                **(
                    row
                    | {
                        "charge_on": date.fromisoformat(installment["due_on"])
                        if installment
                        else None
                    }
                ),
                quote=installment["quote"] if installment else None,
            )
        )
    MembershipDraftCycle.objects.bulk_create(cycles)
    member = MembershipPurchase.objects.create(
        membership=root,
        customer=customer,
        request_key=key,
        fingerprint=reviewed,
        terms_version=VERSION,
        terms_text=data["terms"],
        benefit_rules=data["rules"],
        purpose="complimentary" if data["comped"] else data["operation"],
        send_confirmation=send_confirmation if data["comped"] else True,
        source="staff" if actor else "public",
        confirmation_mode="combined" if combined_booking is not None else "separate",
        actor=actor,
    )
    mandate = (
        MembershipCardMandate.objects.create(
            purchase=member, method=method, text=data["terms"], actor=actor
        )
        if method
        else None
    )
    MembershipBilling.objects.create(purchase=member, mandate=mandate)
    if mandate:
        from .membership_card_setup import replace_future_card

        replace_future_card(method, actor)
    if data["origin"]:
        MembershipOrigin.objects.create(
            purchase=member,
            prior_id=data["origin"]["prior_id"],
            operation=data["operation"],
            places=root.places,
            prior_ends_on=date.fromisoformat(data["origin"]["prior_ends_on"]),
            purchased_on=date.fromisoformat(data["origin"]["purchased_on"]),
            minimum_months=data["origin"]["minimum_months"],
        )
    for cycle in cycles:
        item = row_by_number.get(cycle.number)
        if item:
            MembershipInstallment.objects.create(
                purchase=member,
                number=cycle.number,
                cycle=cycle,
                due_on=item["due_on"],
                quote=item["quote"],
            )
    AuditEvent.objects.create(
        actor=actor,
        action="membership.purchased",
        record_type="membership",
        record_id=str(root.pk),
        changes={
            "kind": root.kind,
            "places": root.places,
            "starts_on": data["starts_on"],
            "ends_on": data["ends_on"],
            "billing": root.billing,
            "comped": data["comped"],
            "operation": data["operation"],
            "prior_id": data["origin"]["prior_id"] if data["origin"] else None,
            "minimum_override": data["minimum_override"],
            "terms_version": VERSION,
            "received": False,
        },
    )
    if data["comped"]:
        queue_confirmation(member)
    else:
        if actor is None:
            from .membership_public_authority import record_acceptance

            record_acceptance(
                proof=authority, purchase=member, card_authorization_id=card_authorization_id
            )
        first = member.installments.first()
        invoice = invoice_for(first, actor=actor, tender=root.expected_method, authority=authority)
        if data.get("paid_visit"):
            from .membership_paid_visit import complete_purchase

            complete_purchase(actor=actor, member=member, offer=data, invoice=invoice)
            return member
        if data.get("first_payment_plan"):
            from .membership_first_split import apply_credit, record

            if data.get("credit"):
                apply_credit(actor=actor, member=member, sale=invoice.sale, plan=data["credit"])
            bank = data["first_payment_plan"].get("recorded_zelle")
            if bank:
                from .membership_bank import apply as apply_bank

                apply_bank(
                    actor=actor, member=member, invoice=invoice, plan=bank, booking=combined_booking
                )
            record(
                actor=actor,
                member=member,
                invoice=invoice,
                plan=data["first_payment_plan"],
                method=method,
            )
            if installment_paid(first):
                queue_confirmation(member)
            return member
        if data.get("credit"):
            from .membership_initial_credit import apply as apply_initial_credit

            apply_initial_credit(actor=actor, member=member, plan=data["credit"])
        if not due_now and data.get("credit"):
            return member
        allocation = full_allocation(invoice.sale)
        if data.get("credit"):
            allocation[0]["net"] = str(
                amount(allocation[0]["net"]) - amount(data["credit"]["amount"])
            )
        operation = request_operation(
            actor=actor,
            sale_id=invoice.sale_id,
            request_key=uuid.uuid5(key, "first-payment"),
            tender=root.expected_method,
            allocation=allocation,
            method_id=method.pk if root.expected_method == "card" else None,
            purpose="member_purchase",
            received_on=received_on,
            public_membership_authority=authority,
        )
        if operation.tender == "card":
            from .payments.jobs import enqueue

            enqueue(kind="payment_dispatch", reference=operation.pk, key=f"dispatch:{operation.pk}")
        else:
            record_manual(actor=actor, operation_id=operation.pk, received=True)
    return member


def card_required(data):
    if data["comped"]:
        return False
    card = (
        amount(data["first_payment_plan"]["card_total"])
        if data.get("first_payment_plan")
        else amount(data.get("first_payment_total", data["installments"][0]["quote"]["total"]))
        if data["installments"] and data["expected_method"] == "card"
        else ZERO
    )
    return data["billing"] == "monthly" or card > ZERO


@transaction.atomic
def invoice_for(installment, *, actor, tender, authority=None, scheduled_claim=None):
    if scheduled_claim is not None:
        if actor is not None or authority is not None:
            raise PermissionDenied
        from .membership_collection_authority import authorize_invoice

        authorize_invoice(scheduled_claim, installment_id=installment.pk, tender=tender)
    else:
        authorize(actor, collect=True, authority=authority)
    installment = MembershipInstallment.objects.select_related("purchase__membership").get(
        pk=installment.pk
    )
    purchase = installment.purchase
    if actor is None and scheduled_claim is None:
        from .membership_public_authority import check_purchase

        check_purchase(authority, purchase)
        if installment.number != 1 or tender != "card":
            raise PermissionDenied
    root = purchase.membership
    quote = installment.quote
    # Later alternate-tender/credit changes require an explicit revised allocation.
    expected = root.expected_method if installment.number == 1 else "card"
    if tender != expected:
        raise ValidationError("Review the membership installment payment method before collecting.")
    key = lock_request(uuid.uuid5(purchase.request_key, f"installment:{installment.number}"))
    existing = MembershipInvoice.objects.filter(installment=installment).first()
    if existing:
        return existing
    sale = FinancialSale.objects.create(
        creation_key=key,
        fingerprint=fingerprint(
            {"membership": root.pk, "installment": installment.number, "quote": quote}
        ),
        customer=purchase.customer,
        kind="membership",
        customer_label=purchase.customer.last_name,
        subtotal=quote["subtotal"],
        processing_fee=quote["processing_fee"],
        sales_tax=quote["sales_tax"],
        total=quote["total"],
        tax_rate=quote["rates"]["tax_rate"],
        fee_rate=quote["rates"]["card_fee_rate"],
        policy_id_at_sale=root.fee_policy_id,
        service_at=timezone.make_aware(
            datetime.combine(installment.cycle.starts_on, time.min), NEW_YORK
        ),
        actor=actor,
    )
    line = quote["lines"][0]
    FinancialLine.objects.create(
        sale=sale,
        position=1,
        category="membership_" + root.kind,
        description=line["label"],
        quantity=line["quantity"],
        unit_price=line["unit_price"],
        net=quote["subtotal"],
        fee=quote["processing_fee"],
        item_tax=ZERO,
        fee_tax=ZERO,
        taxable=False,
    )
    return MembershipInvoice.objects.create(installment=installment, sale=sale)


def installment_paid(installment):
    try:
        sale = installment.invoice.sale
    except MembershipInvoice.DoesNotExist:
        return False
    from .membership_funding import sale_needs_review

    return not sale_needs_review(sale) and settled(sale) >= total(sale)


def membership_status(member, *, on=None):
    on = on or today()
    root = member.membership
    billing = member.billing_state
    if billing.stopped_on and (billing.stopped_on <= on or billing.stopped_on <= root.starts_on):
        return "cancelled"
    if root.ends_on < on:
        return "expired"
    from .membership_funding import member_needs_review

    if member_needs_review(member):
        return "review"
    if member.purpose != "complimentary":
        required = member.installments.select_related("invoice__sale", "cycle").order_by("number")
        if billing.stopped_on:
            required = required.filter(cycle__starts_on__lt=billing.stopped_on)
        installments = list(required)
        if not installments or not installment_paid(installments[0]):
            return "pending"
        if any(item.due_on <= on and not installment_paid(item) for item in installments):
            return "overdue"
    return "scheduled" if root.starts_on > on else "active"


def payment_updated(operation):
    from .membership_cancellations import refund_updated

    refund_updated(operation)
    try:
        invoice = operation.sale.membership_invoice
    except MembershipInvoice.DoesNotExist:
        return
    if installment_paid(invoice.installment):
        from .payments.models import PaymentFollowup

        PaymentFollowup.objects.filter(
            operation__sale=operation.sale,
            operation__state__in=["declined", "cancelled"],
            resolved_at__isnull=True,
        ).update(resolved_at=timezone.now())
    if (
        operation.kind == "receipt"
        and invoice.installment.number == 1
        and installment_paid(invoice.installment)
    ):
        queue_confirmation(invoice.installment.purchase)


def queue_confirmation(member):
    if member.membership.snapshot.get("paid_visit_purchase"):
        from .membership_paid_visit import queue_confirmation as queue_paid_visit

        return queue_paid_visit(member)
    stopped = False
    if member.confirmation_mode == "combined":
        from .membership_records import MembershipArrivalClosure
        from .membership_schema import available

        stopped = (
            available("core_membershiparrivalclosure")
            and MembershipArrivalClosure.objects.filter(
                intent__purchase=member, intent__progress__status="stopped"
            ).exists()
        )
        if not stopped:
            from .membership_arrival_pending import queue_ready

            queue_ready(member)
            return
    if not member.send_confirmation or not member.customer.email or member.cancellations.exists():
        return
    from django.urls import reverse

    from .communications.models import MessageDelivery
    from .communications.services import enqueue
    from .date_display import display_date

    root = member.membership
    if MessageDelivery.objects.filter(dedupe_key=f"membership-confirmation:{member.pk}").exists():
        return
    from .customer_credit import applied

    paid, credited = ZERO, ZERO
    for item in member.installments.select_related("invoice__sale"):
        try:
            paid += received(item.invoice.sale)
            credited += applied(item.invoice.sale)
        except MembershipInvoice.DoesNotExist:
            pass
    content = [
        f"Dear Family {member.customer.last_name},",
        "",
        f"Your {root.get_kind_display()} Membership begins on {display_date(root.starts_on, 'l, F j, Y')} and continues through {display_date(root.ends_on, 'l, F j, Y')}.",
        f"{root.places} {root.get_kind_display()} Membership" + ("s" if root.places != 1 else ""),
        "",
        "Enjoy two free play sessions per membership each month, then just $5.99 for each additional play session that month. Your membership also includes two free adults for every visit, 25% off supervised play, and 15% off parties."
        if root.kind == "subscription"
        else "Enjoy one free visit per membership each day, with two free adults, plus 15% off parties. Unlimited Membership benefits exclude supervised play and Chol Hamoed. You may book those visits at full price.",
        "Your membership is complimentary."
        if member.purpose == "complimentary"
        else f"Your payment of ${paid:.2f} was received."
        if paid
        else "Your membership payment is covered by customer credit.",
        "The purchased term ends without automatic renewal.",
    ]
    next_payment = member.installments.filter(number__gt=1).order_by("number").first()
    subject = f"Your Monkey Do {root.get_kind_display()} Membership is ready!"
    message_kind = "membership_confirmation"
    origin = getattr(member, "origin", None)
    if origin and member.purpose != "complimentary":
        label = f"{root.places} {root.get_kind_display()} Membership" + (
            "s" if root.places != 1 else ""
        )
        dates = f"Begins: {display_date(root.starts_on, 'F j, Y')}\nEnds: {display_date(root.ends_on, 'F j, Y')}"
        content = [
            f"Dear Family {member.customer.last_name},",
            "",
            "You're all set for more Monkey Do adventures!",
            "",
        ]
        if origin.operation == "renewal":
            subject = "Your Monkey Do membership is renewed!"
            message_kind = "membership_renewal"
            content += ["Your renewed membership is ready:", "", label, dates]
            previous_kind = origin.prior.membership.kind
            if previous_kind != root.kind:
                content += [
                    "",
                    f"Your membership is changing from {origin.prior.membership.get_kind_display()} to {root.get_kind_display()}.",
                ]
            content += ["", "You can always renew your membership."]
        else:
            subject = "More Monkey Do adventures are ready!"
            message_kind = "membership_addition"
            content += [
                f"You've added {label}.",
                "",
                f"These memberships begin on {display_date(root.starts_on, 'F j, Y')} and continue through {display_date(root.ends_on, 'F j, Y')}. Your membership can always be renewed.",
            ]
        content += [
            "",
            "Your membership payment is covered by customer credit."
            if not paid and credited
            else f"Your first payment of ${paid:.2f} was received."
            if root.billing == "monthly"
            else f"Your payment of ${paid:.2f} was received for a {root.months}-month membership.",
        ]
        if origin.operation == "addition":
            content += [
                "",
                "Your existing memberships keep their own dates and benefits.",
                "After the initial three months, qualifying renewals do not require a new three-month minimum.",
            ]
        content += [
            "",
            "The purchased term ends without automatic renewal.",
        ]
    elif member.purpose == "complimentary":
        subject = "A little more Monkey Do fun, on us!"
    if stopped and message_kind == "membership_confirmation":
        subject = "Your Monkey Do membership purchase"
    if credited:
        content += ["", f"A customer credit of ${credited:.2f} was applied to this purchase."]
    if next_payment:
        content.append(
            f"Your next scheduled membership payment is ${next_payment.quote['total']} on {display_date(next_payment.due_on, 'F j, Y')}."
        )
    if origin and member.purpose != "complimentary":
        content += [
            "",
            settings.BOOKING_STAGING_ORIGIN + reverse("schedule"),
            "",
            "Get ready to go bananas,",
            "The Monkey Do team",
        ]
    enqueue(
        key=f"membership-confirmation:{member.pk}",
        kind=message_kind,
        recipient=member.customer.email,
        subject=subject,
        text="\n".join(content),
        customer=member.customer,
        membership=member,
        actor=member.actor,
    )
