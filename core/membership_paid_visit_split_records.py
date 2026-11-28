"""A verified partial remainder and independent, explicitly authorized card attempts."""

from django.conf import settings
from django.db import models

from .payments.models import FinancialFact


class MembershipPaidVisitSplit(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    intent = models.OneToOneField(
        "core.MembershipPaidVisitIntent", on_delete=models.PROTECT, related_name="split_payment"
    )
    previous = models.ForeignKey("core.PaymentOperation", on_delete=models.PROTECT)
    operation = models.OneToOneField(
        "core.PaymentOperation",
        to_field="request_key",
        on_delete=models.PROTECT,
        related_name="paid_visit_split_receipt",
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    facts = models.JSONField()
    fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class MembershipPaidVisitSplitCard(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    split = models.ForeignKey(
        MembershipPaidVisitSplit, on_delete=models.PROTECT, related_name="card_attempts"
    )
    sequence = models.PositiveIntegerField()
    previous = models.OneToOneField(
        "core.PaymentOperation", on_delete=models.PROTECT, related_name="paid_visit_split_successor"
    )
    operation = models.OneToOneField(
        "core.PaymentOperation",
        to_field="request_key",
        on_delete=models.PROTECT,
        related_name="paid_visit_split_card",
    )
    method = models.ForeignKey("core.PaymentMethod", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    review = models.JSONField()
    fingerprint = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["split", "sequence"], name="paid_visit_split_card_order"
            ),
        ]
