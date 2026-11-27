"""Durable financial dispatch: an uncertain POST is never automatically replayed."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from core.models import Booking
from core.permissions import require_actor

from .amounts import amount
from .gateway import Gateway, ProviderFailure, reference
from .ledger import enabled, fingerprint, record_result, writes_allowed
from .models import PaymentEvent, PaymentMethod, PaymentOperation, ProviderObservation


def verify_transaction(operation, data, *, allow_declined=False, allow_reversal=False):
    """Reconcile provider evidence against immutable application identity/amount."""
    if not isinstance(data, dict):
        raise ProviderFailure("invalid_provider_transaction")
    provider_id = reference(data.get("id"))
    if getattr(operation, "provider_reference", "") and provider_id != operation.provider_reference:
        raise ProviderFailure("provider_reference_mismatch")
    if amount(data.get("amount_details", {}).get("amount")) != operation.amount:
        raise ProviderFailure("provider_amount_mismatch")
    meta = data.get("custom_fields", {})
    details = data.get("transaction_details", {})
    if operation.kind == "receipt":
        if (
            meta.get("custom1") != str(operation.pk)
            or meta.get("custom2") != "monkeydo:sandbox"
            or details.get("type") != "charge"
        ):
            raise ProviderFailure("provider_identity_mismatch")
    elif operation.kind == "refund":
        if (
            reference(details.get("reference_number")) != operation.original.provider_reference
            or details.get("type") != "credit"
        ):
            raise ProviderFailure("provider_identity_mismatch")
        # A provider-dashboard correction may lack app metadata, but is linked
        # to the exact original charge and amount and is imported by owner only.
        if meta.get("custom1") not in (None, "", str(operation.pk)):
            raise ProviderFailure("provider_identity_mismatch")
    elif provider_id != operation.original.provider_reference:
        raise ProviderFailure("provider_identity_mismatch")
    status = data.get("status_details", {}).get("status")
    if operation.kind == "void":
        if status != "voided":
            raise ProviderFailure("provider_not_voided")
    elif status not in (
        {"captured", "settled"}
        | ({"declined"} if allow_declined else set())
        | ({"voided", "returned"} if allow_reversal else set())
    ):
        # Authorization, partial/unknown/submitted and a voided original are not
        # evidence of the requested successful receipt/refund.
        raise ProviderFailure("provider_not_captured")
    return provider_id


def observe(operation, data, *, allow_declined=False, allow_reversal=False):
    provider_id = verify_transaction(
        operation, data, allow_declined=allow_declined, allow_reversal=allow_reversal
    )
    when = parse_datetime(data.get("created_at") or "")
    if when is not None and timezone.is_naive(when):
        raise ProviderFailure("invalid_provider_timestamp")
    settled = parse_date(data.get("settled_date") or "")
    batch = data.get("transaction_details", {}).get("batch_id")
    card = data.get("card_details") or {}
    brand, last_four = card.get("card_type", ""), card.get("last4", "")
    if brand and brand not in {"Visa", "MasterCard", "Amex", "Discover", "JCB", "Diners"}:
        raise ProviderFailure("invalid_transaction_card_metadata")
    if last_four and (
        not isinstance(last_four, str)
        or len(last_four) != 4
        or not last_four.isascii()
        or not last_four.isdigit()
    ):
        raise ProviderFailure("invalid_transaction_card_metadata")
    facts = {
        "reference": provider_id,
        "status": data["status_details"]["status"],
        "amount": str(operation.amount),
        "occurred": when.isoformat() if when else None,
        "settled": settled.isoformat() if settled else None,
        "batch": reference(batch) if batch else "",
        "brand": brand,
        "last_four": last_four,
    }
    ProviderObservation.objects.get_or_create(
        operation=operation,
        fingerprint=fingerprint(facts),
        defaults={
            "provider_reference": provider_id,
            "provider_status": facts["status"],
            "amount": operation.amount,
            "occurred_at": when,
            "settled_date": settled,
            "batch_reference": facts["batch"],
            "brand": brand,
            "last_four": last_four,
        },
    )
    # Voiding a transaction updates the original: its created_at is the charge
    # date, not the void date. Keep confirmation time separately for that case.
    return provider_id, when if operation.kind != "void" else None


def refresh_completed(operation):
    """Read-only settlement refresh; reversal evidence needs an owner allocation."""
    if (
        operation.tender != "card"
        or operation.state != "succeeded"
        or not operation.provider_reference
    ):
        return operation
    data = Gateway().transaction(operation.provider_reference)
    observe(operation, data, allow_reversal=operation.kind == "receipt")
    if data["status_details"]["status"] in {"voided", "returned"}:
        from core.models import OwnerNotice

        from .models import PaymentFollowup

        with transaction.atomic():
            operation = PaymentOperation.objects.select_for_update().get(pk=operation.pk)
            _, created = PaymentEvent.objects.get_or_create(
                operation=operation,
                state=operation.state,
                source="provider",
                code="external_correction_review",
            )
            if created:
                PaymentFollowup.objects.update_or_create(
                    operation=operation,
                    defaults={"plan": "owner_review", "resolved_at": None},
                )
                OwnerNotice.objects.create(
                    customer=operation.sale.customer,
                    subject="Provider payment correction needs review",
                    details={
                        "kind": "payment_correction",
                        "operation_id": str(operation.pk),
                        "provider_reference": operation.provider_reference,
                    },
                )
    return operation


@transaction.atomic
def begin_dispatch(operation_id):
    candidate = PaymentOperation.objects.select_related("sale").get(pk=operation_id)
    if candidate.sale.kind == "membership":
        from core.membership_reservations import lock_customer

        lock_customer(candidate.sale.customer_id)
    operation = PaymentOperation.objects.select_for_update().get(pk=operation_id)
    if operation.tender != "card":
        raise ValidationError("Non-card receipt must be explicitly recorded by staff.")
    if operation.state != "ready":
        return None
    if operation.sale.kind == "membership":
        from core.membership_sales import enabled as membership_enabled

        membership_enabled()
    if operation.actor_id is None:
        from core.membership_public_authority import authorize_dispatch

        authorize_dispatch(operation)
    else:
        require_actor(operation.actor, "core.collect_payment", owner=operation.kind != "receipt")
    if operation.sale.kind == "membership" and operation.kind != "receipt":
        from core.membership_cancellations import unrecorded_provider_return

        if unrecorded_provider_return(operation.original):
            operation.state = "cancelled"
            operation.result_code = "external_correction_review"
            operation.completed_at = timezone.now()
            operation.save(update_fields=["state", "result_code", "completed_at"])
            PaymentEvent.objects.create(
                operation=operation,
                state="cancelled",
                source="worker",
                code="external_correction_review",
            )
            return None
    if operation.kind == "receipt":
        booking = (
            Booking.objects.select_for_update().get(pk=operation.sale.booking_id)
            if operation.sale.booking_id
            else None
        )
        method = PaymentMethod.objects.select_for_update().get(pk=operation.method_id)
        invalid = (
            method.state != "active"
            or not method.provider_method
            or method.customer_id != operation.sale.customer_id
        )
        if operation.sale.kind == "membership":
            from core.membership_funding import member_needs_review

            invoice = operation.sale.membership_invoice
            stopped = invoice.installment.purchase.billing_state.stopped_on
            invalid |= bool(stopped and invoice.installment.cycle.starts_on >= stopped)
            invalid |= member_needs_review(invoice.installment.purchase)
        if booking:
            invalid |= booking.workflow != "integrated_v1" or (
                operation.sale.kind == "visit"
                and operation.sale.booking_version != booking.edit_version
            )
        if invalid:
            operation.state = "cancelled"
            operation.result_code = "changed_before_dispatch"
            operation.completed_at = timezone.now()
            operation.save(update_fields=["state", "result_code", "completed_at"])
            PaymentEvent.objects.create(
                operation=operation,
                state="cancelled",
                source="worker",
                code="changed_before_dispatch",
            )
            return None
    operation.state = "sending"
    operation.dispatched_at = timezone.now()
    operation.save(update_fields=["state", "dispatched_at"])
    PaymentEvent.objects.create(operation=operation, state="sending", source="provider")
    return operation


def execute(operation_id):
    enabled()
    writes_allowed()
    existing = PaymentOperation.objects.get(pk=operation_id)
    if existing.tender == "card" and existing.state in {"succeeded", "declined", "cancelled"}:
        return existing
    gateway = Gateway()  # Fail before reserving/sending if configuration is absent.
    operation = begin_dispatch(operation_id)
    if operation is None:
        return PaymentOperation.objects.get(pk=operation_id)
    try:
        response = getattr(
            gateway, {"receipt": "charge", "refund": "refund", "void": "void"}[operation.kind]
        )(operation)
        if response.get("status_code") == "D":
            return record_result(
                operation_id=operation.pk,
                state="declined",
                source="provider",
                code="declined",
                provider_reference=reference(response["reference_number"])
                if response.get("reference_number")
                else "",
            )
        if response.get("status_code") != "A":
            raise ProviderFailure("provider_outcome_unknown")
        if operation.kind == "void":
            provider_id = operation.original.provider_reference
        else:
            provider_id = reference(response.get("reference_number"))
        # Retain only a validated safe transaction reference before a GET. If
        # reconciliation or local commit fails, no second financial POST occurs.
        with transaction.atomic():
            current = PaymentOperation.objects.select_for_update().get(pk=operation.pk)
            if current.state == "sending":
                current.provider_reference = provider_id
                current.save(update_fields=["provider_reference"])
        data = gateway.transaction(provider_id)
        provider_id, occurred_at = observe(operation, data)
        return record_result(
            operation_id=operation.pk,
            state="succeeded",
            source="provider",
            provider_reference=provider_id,
            code="captured",
            occurred_at=occurred_at,
        )
    except (ProviderFailure, ValidationError, TypeError, ValueError, AttributeError):
        return record_result(
            operation_id=operation.pk,
            state="unknown",
            source="provider",
            code="provider_review_required",
        )


def reconcile(*, operation_id, actor=None, provider_reference=None):
    enabled()
    operation = PaymentOperation.objects.select_related("original").get(pk=operation_id)
    if actor is not None:
        require_actor(actor, "core.review_payment", owner=True)
    if operation.state == "succeeded":
        return refresh_completed(operation)
    if operation.state in {"declined", "cancelled"}:
        return operation
    if operation.state == "ready":
        raise ValidationError("This operation has not been dispatched.")
    if provider_reference is not None and actor is None:
        raise ValidationError("Only an owner can supply a reconciliation reference.")
    provider_id = provider_reference or operation.provider_reference
    if not provider_id:
        raise ValidationError("Owner review is needed to identify the provider transaction.")
    gateway = Gateway()
    try:
        data = gateway.transaction(reference(provider_id))
        verified, occurred_at = observe(operation, data, allow_declined=True)
    except (ProviderFailure, ValidationError, TypeError, ValueError, AttributeError):
        return record_result(
            operation_id=operation.pk,
            state="unknown",
            source="reconcile",
            code="provider_review_required",
            actor=actor,
        )
    return record_result(
        operation_id=operation.pk,
        state="declined"
        if data.get("status_details", {}).get("status") == "declined"
        else "succeeded",
        source="reconcile",
        provider_reference=verified,
        code="declined"
        if data.get("status_details", {}).get("status") == "declined"
        else "captured",
        actor=actor,
        occurred_at=occurred_at,
    )
