"""Explicit application disposal; provider deletion never erases transaction history."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import AuditEvent
from core.permissions import require_actor

from .gateway import Gateway, ProviderFailure, reference
from .ledger import enabled, writes_allowed
from .models import PaymentMethod, PaymentOperation


def outstanding(method):
    from core.membership_records import MembershipBilling
    from core.membership_sales import installment_paid

    if (
        method.agreements.filter(resolved_at__isnull=True).exists()
        or PaymentOperation.objects.filter(
            method=method, state__in=["ready", "sending", "unknown", "action"]
        ).exists()
    ):
        return True
    for billing in MembershipBilling.objects.filter(mandate__method=method).select_related(
        "purchase__membership"
    ):
        # Expiry never settles an unpaid installment. Conversely, a prepaid,
        # fully paid term does not create a continuing scheduled-card obligation.
        installments = billing.purchase.installments.all()
        if billing.stopped_on is not None:
            installments = installments.filter(cycle__starts_on__lt=billing.stopped_on)
        if any(not installment_paid(item) for item in installments.select_related("invoice__sale")):
            return True
    return False


def queue_disposal(method):
    if method.state == "active" and not method.reusable and not outstanding(method):
        from .jobs import enqueue

        return enqueue(kind="method_remove", reference=method.pk, key=f"method-remove:{method.pk}")


def expire_membership_sources():
    """Queue an unwanted source only after all fixed-term obligations finish."""
    enabled()
    methods = (
        PaymentMethod.objects.filter(
            state="active", reusable=False, membership_mandates__isnull=False
        )
        .distinct()
        .order_by("created_at", "pk")[:100]
    )
    return sum(bool(queue_disposal(method)) for method in methods)


@transaction.atomic
def expire_unused_setups():
    """Discard abandoned setup cards, including uncompleted future-use choices."""
    from .models import PaymentSetup

    enabled()
    expired = PaymentSetup.objects.select_for_update().filter(
        expires_at__lt=timezone.now(),
        state="succeeded",
        method__booking__isnull=True,
        method__state="active",
    )[:100]
    count = 0
    for setup in expired:
        method = PaymentMethod.objects.select_for_update().get(pk=setup.method_id)
        if (
            method.booking_id is not None
            or method.membership_mandates.exists()
            or outstanding(method)
        ):
            continue
        method.reusable = False
        method.save(update_fields=["reusable"])
        queue_disposal(method)
        count += 1
    return count


@transaction.atomic
def retire_future_use(*, actor, method_id):
    enabled()
    require_actor(actor, "core.change_customer")
    method = PaymentMethod.objects.select_for_update().get(pk=method_id)
    method.reusable = False
    method.save(update_fields=["reusable"])
    AuditEvent.objects.create(
        actor=actor,
        action="payment.future_use_removed",
        record_type="payment_method",
        record_id=str(method.pk),
        changes={"last_four": method.last_four},
    )
    queue_disposal(method)
    return method


@transaction.atomic
def begin_removal(method_id):
    method = PaymentMethod.objects.select_for_update().get(pk=method_id)
    if method.state == "removed":
        return None
    if method.reusable or outstanding(method):
        raise ValidationError(
            "This card is still retained or needed by an outstanding booking/payment."
        )
    if method.state == "removing":
        raise ValidationError("Provider deletion needs review before another request.")
    if method.state != "active":
        raise ValidationError("Resolve this card status before deleting it.")
    method.state = "removing"
    method.save(update_fields=["state"])
    return method


def remove_unused(method_id):
    enabled()
    writes_allowed()
    gateway = Gateway()
    method = begin_removal(method_id)
    if method is None:
        return PaymentMethod.objects.get(pk=method_id)
    provider_id = reference(method.provider_method)
    try:
        gateway.delete_method(provider_id)
    except ProviderFailure as error:
        # Removal is already enforced in the app; provider outcome is uncertain.
        # Keep the private reference for explicit lookup rather than claiming
        # all derived provider references are irrevocably unchargeable.
        if error.code != "provider_not_found":
            return PaymentMethod.objects.get(pk=method_id)
    return mark_removed(method_id)


def mark_removed(method_id):
    with transaction.atomic():
        current = PaymentMethod.objects.select_for_update().get(pk=method_id)
        if current.reusable or outstanding(current):
            raise ValidationError(
                "Card responsibilities changed during deletion; owner review required."
            )
        current.state = "removed"
        current.provider_method = None
        current.removed_at = timezone.now()
        current.save(update_fields=["state", "provider_method", "removed_at"])
        AuditEvent.objects.create(
            actor=None,
            action="payment.booking_method_removed",
            record_type="payment_method",
            record_id=str(current.pk),
            changes={"last_four": current.last_four},
        )
        return current


def reconcile_removal(*, actor, method_id):
    enabled()
    require_actor(actor, "core.review_payment", owner=True)
    method = PaymentMethod.objects.get(pk=method_id, state="removing")
    try:
        Gateway().method(reference(method.provider_method))
    except ProviderFailure as error:
        if error.code == "provider_not_found":
            return mark_removed(method_id)
    return method
