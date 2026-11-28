"""Conditional use of an already-paid visit, before a first card result is known."""

import uuid

from django.conf import settings
from django.db import models

from .payments.models import FinancialFact


class MembershipPaidVisitIntent(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    purchase = models.OneToOneField(
        "core.MembershipPurchase", on_delete=models.PROTECT, related_name="paid_visit_intent"
    )
    booking = models.ForeignKey(
        "core.Booking", on_delete=models.PROTECT, related_name="paid_visit_intents"
    )
    source_sale = models.ForeignKey("core.FinancialSale", on_delete=models.PROTECT)
    operation = models.OneToOneField(
        "core.PaymentOperation",
        null=True,
        on_delete=models.PROTECT,
        related_name="paid_visit_intent",
    )
    conversion_key = models.UUIDField(unique=True)
    fingerprint = models.CharField(max_length=64)
    offer = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class MembershipPaidVisitRelease(FinancialFact):
    intent = models.OneToOneField(
        MembershipPaidVisitIntent,
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="release",
    )
    request_key = models.UUIDField(default=uuid.uuid4, unique=True)
    kind = models.CharField(
        max_length=10, choices=[("completed", "Completed"), ("stopped", "Stopped")]
    )
    conversion = models.OneToOneField(
        "core.VisitMembershipConversion",
        null=True,
        on_delete=models.PROTECT,
        related_name="paid_visit_release",
    )
    reason = models.CharField(max_length=500, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind="completed", conversion__isnull=False)
                | models.Q(kind="stopped", conversion__isnull=True),
                name="paid_visit_release_evidence",
            )
        ]


class MembershipPaidVisitRecovery(FinancialFact):
    """A fresh, explicit card authority; never a mutation of an earlier attempt."""

    id = models.UUIDField(primary_key=True, editable=False)
    intent = models.ForeignKey(
        MembershipPaidVisitIntent, on_delete=models.PROTECT, related_name="recoveries"
    )
    sequence = models.PositiveIntegerField()
    previous = models.OneToOneField(
        "core.PaymentOperation", on_delete=models.PROTECT, related_name="paid_visit_successor"
    )
    # Its deferred FK permits authority insertion before the exact ledger request.
    operation = models.OneToOneField(
        "core.PaymentOperation",
        to_field="request_key",
        on_delete=models.PROTECT,
        related_name="paid_visit_recovery",
    )
    method = models.ForeignKey("core.PaymentMethod", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    review = models.JSONField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["intent", "sequence"], name="paid_visit_recovery_order"
            ),
        ]


class MembershipPaidVisitCancellation(FinancialFact):
    """Owner authority to release an unused source after membership cancellation."""

    release = models.OneToOneField(
        MembershipPaidVisitRelease,
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="cancellation_decision",
    )
    cancellation = models.ForeignKey("core.MembershipCancellation", on_delete=models.PROTECT)
    request_key = models.UUIDField(unique=True)
    facts = models.JSONField()
    fingerprint = models.CharField(max_length=64)
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class MembershipPaidVisitCardStorage(FinancialFact):
    """Storage consent for this unapplied purchase, separate from future billing."""

    authorization = models.OneToOneField(
        "core.MembershipCardAuthorization",
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="paid_visit_storage",
    )
    intent = models.ForeignKey(
        MembershipPaidVisitIntent, on_delete=models.PROTECT, related_name="card_storage"
    )
    previous = models.ForeignKey("core.PaymentOperation", on_delete=models.PROTECT)
    facts = models.JSONField()
    fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class MembershipPaidVisitManualPayment(FinancialFact):
    """A received replacement payment; unused card fees are not collected."""

    id = models.UUIDField(primary_key=True, editable=False)
    intent = models.OneToOneField(
        MembershipPaidVisitIntent, on_delete=models.PROTECT, related_name="manual_payment"
    )
    previous = models.ForeignKey("core.PaymentOperation", on_delete=models.PROTECT)
    operation = models.OneToOneField(
        "core.PaymentOperation",
        to_field="request_key",
        on_delete=models.PROTECT,
        related_name="paid_visit_manual_payment",
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    facts = models.JSONField()
    fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
