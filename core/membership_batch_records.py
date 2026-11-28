"""One accepted renewal checkout, with separate immutable purchased cohorts."""

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from .payments.models import FinancialFact


class MembershipRenewalBatch(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    customer = models.ForeignKey("core.Customer", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    facts = models.JSONField(encoder=DjangoJSONEncoder)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    tender = models.CharField(
        max_length=5, choices=[("cash", "Cash"), ("check", "Check"), ("zelle", "Zelle")]
    )
    received_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="renewal_batch_positive"),
            models.CheckConstraint(
                condition=models.Q(tender__in=["cash", "check", "zelle"]),
                name="renewal_batch_manual",
            ),
        ]


class MembershipRenewalBatchPart(FinancialFact):
    batch = models.ForeignKey(
        MembershipRenewalBatch, on_delete=models.PROTECT, related_name="parts"
    )
    purchase = models.OneToOneField(
        "core.MembershipPurchase",
        to_field="request_key",
        db_column="purchase_request_key",
        on_delete=models.PROTECT,
        related_name="renewal_batch_part",
    )
    prior = models.ForeignKey("core.MembershipPurchase", on_delete=models.PROTECT)
    position = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    facts = models.JSONField(encoder=DjangoJSONEncoder)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "position"], name="renewal_batch_one_position"
            ),
            models.CheckConstraint(
                condition=models.Q(position__gte=1, amount__gt=0),
                name="renewal_batch_part_positive",
            ),
        ]


class MembershipRenewalBatchMessage(FinancialFact):
    batch = models.ForeignKey(
        MembershipRenewalBatch, on_delete=models.PROTECT, related_name="messages"
    )
    message = models.OneToOneField("core.MessageDelivery", on_delete=models.PROTECT)


class MembershipRenewalBatchBank(FinancialFact):
    """One verified transfer; the batch parts allocate this source, not new transfers."""

    batch = models.OneToOneField(
        MembershipRenewalBatch,
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="bank_receipt",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    received_on = models.DateField()
    sender = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="renewal_bank_positive")
        ]
