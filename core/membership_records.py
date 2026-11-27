"""Accepted membership facts extend the existing stable M-numbered identity."""

import uuid

from django.conf import settings
from django.db import models

from .payments.models import FinancialFact


class MembershipPurchase(FinancialFact):
    membership = models.OneToOneField(
        "core.MembershipDraft",
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="purchase",
    )
    customer = models.ForeignKey(
        "core.Customer", on_delete=models.PROTECT, related_name="membership_purchases"
    )
    request_key = models.UUIDField(unique=True)
    fingerprint = models.CharField(max_length=64)
    terms_version = models.CharField(max_length=60)
    terms_text = models.TextField()
    benefit_rules = models.JSONField()
    purpose = models.CharField(
        max_length=20,
        choices=[
            (x, x.title())
            for x in ("purchase", "addition", "renewal", "conversion", "complimentary")
        ],
    )
    send_confirmation = models.BooleanField(default=True)
    confirmation_mode = models.CharField(
        max_length=12,
        default="separate",
        choices=[("separate", "Membership only"), ("combined", "With booking")],
    )
    source = models.CharField(
        max_length=8, default="staff", choices=[("staff", "Staff"), ("public", "Customer")]
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    accepted_at = models.DateTimeField(auto_now_add=True)

    @property
    def membership_number(self):
        return self.membership.membership_number


class MembershipInstallment(FinancialFact):
    purchase = models.ForeignKey(
        MembershipPurchase, on_delete=models.PROTECT, related_name="installments"
    )
    number = models.PositiveIntegerField()
    cycle = models.OneToOneField(
        "core.MembershipDraftCycle", on_delete=models.PROTECT, related_name="installment"
    )
    due_on = models.DateField(db_index=True)
    quote = models.JSONField()

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(
                fields=["purchase", "number"], name="membership_installment_unique_number"
            )
        ]


class MembershipInvoice(FinancialFact):
    installment = models.OneToOneField(
        MembershipInstallment, on_delete=models.PROTECT, related_name="invoice"
    )
    sale = models.OneToOneField(
        "core.FinancialSale", on_delete=models.PROTECT, related_name="membership_invoice"
    )


class MembershipCardMandate(FinancialFact):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase = models.ForeignKey(
        MembershipPurchase, on_delete=models.PROTECT, related_name="mandates"
    )
    method = models.ForeignKey(
        "core.PaymentMethod", on_delete=models.PROTECT, related_name="membership_mandates"
    )
    text = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    accepted_at = models.DateTimeField(auto_now_add=True)


class MembershipBilling(models.Model):
    purchase = models.OneToOneField(
        MembershipPurchase, primary_key=True, on_delete=models.PROTECT, related_name="billing_state"
    )
    mandate = models.ForeignKey(
        MembershipCardMandate, null=True, on_delete=models.PROTECT, related_name="billing_states"
    )
    stopped_on = models.DateField(null=True)
    revision = models.PositiveIntegerField(default=1)
