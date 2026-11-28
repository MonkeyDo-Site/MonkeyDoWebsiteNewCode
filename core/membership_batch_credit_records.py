"""Accepted combined renewals funded by existing credit, never a new receipt."""

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from .payments.models import FinancialFact


class MembershipCreditRenewalBatch(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    customer = models.ForeignKey("core.Customer", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    facts = models.JSONField(encoder=DjangoJSONEncoder)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def tender(self):
        return "credit"

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="credit_renewal_positive")
        ]


class MembershipCreditRenewalPart(FinancialFact):
    batch = models.ForeignKey(
        MembershipCreditRenewalBatch, on_delete=models.PROTECT, related_name="parts"
    )
    purchase = models.OneToOneField(
        "core.MembershipPurchase",
        to_field="request_key",
        db_column="purchase_request_key",
        on_delete=models.PROTECT,
        related_name="credit_renewal_batch_part",
    )
    prior = models.ForeignKey("core.MembershipPurchase", on_delete=models.PROTECT)
    position = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    facts = models.JSONField(encoder=DjangoJSONEncoder)
    funding_offer = models.JSONField(encoder=DjangoJSONEncoder)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["batch", "position"], name="credit_renewal_position"),
            models.CheckConstraint(
                condition=models.Q(position__gte=1, amount__gt=0),
                name="credit_renewal_part_positive",
            ),
        ]


class MembershipCreditRenewalMessage(FinancialFact):
    batch = models.ForeignKey(
        MembershipCreditRenewalBatch, on_delete=models.PROTECT, related_name="messages"
    )
    message = models.OneToOneField("core.MessageDelivery", on_delete=models.PROTECT)
