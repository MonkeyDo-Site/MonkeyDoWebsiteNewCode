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
