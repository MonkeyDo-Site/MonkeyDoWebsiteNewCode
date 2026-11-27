"""Existing paid money transferred to customer credit, never a second receipt."""

from django.conf import settings
from django.db import models

from .payments.models import FinancialFact


class VisitMembershipConversion(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    booking = models.OneToOneField(
        "core.Booking", on_delete=models.PROTECT, related_name="membership_conversion"
    )
    purchase = models.ForeignKey(
        "core.MembershipPurchase", on_delete=models.PROTECT, related_name="visit_conversions"
    )
    original_quote = models.ForeignKey(
        "core.BookingQuote", on_delete=models.PROTECT, related_name="original_conversions"
    )
    updated_quote = models.OneToOneField(
        "core.BookingQuote", on_delete=models.PROTECT, related_name="conversion"
    )
    fingerprint = models.CharField(max_length=64)
    details = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class CustomerCreditIssue(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    conversion = models.ForeignKey(
        VisitMembershipConversion, on_delete=models.PROTECT, related_name="credits"
    )
    customer = models.ForeignKey(
        "core.Customer", on_delete=models.PROTECT, related_name="credit_issues"
    )
    original = models.ForeignKey(
        "core.PaymentOperation", on_delete=models.PROTECT, related_name="credit_issues"
    )
    allocation = models.JSONField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="customer_credit_issue_positive"
            )
        ]


class CustomerCreditApplication(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    customer = models.ForeignKey("core.Customer", on_delete=models.PROTECT)
    sale = models.ForeignKey(
        "core.FinancialSale", on_delete=models.PROTECT, related_name="credit_applications"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    fingerprint = models.CharField(max_length=64)
    details = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="customer_credit_application_positive"
            )
        ]


class CustomerCreditAllocation(FinancialFact):
    application = models.ForeignKey(
        CustomerCreditApplication, on_delete=models.PROTECT, related_name="allocations"
    )
    issue = models.ForeignKey(
        CustomerCreditIssue, on_delete=models.PROTECT, related_name="applications"
    )
    allocation = models.JSONField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["application", "issue"], name="customer_credit_application_issue_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="customer_credit_allocation_positive"
            ),
        ]


class CustomerCreditCorrection(FinancialFact):
    """An owner changes unused credit; neither kind represents a cash refund."""

    id = models.UUIDField(primary_key=True, editable=False)
    customer = models.ForeignKey(
        "core.Customer", on_delete=models.PROTECT, related_name="credit_corrections"
    )
    kind = models.CharField(
        max_length=7, choices=[("remove", "Remove credit"), ("restore", "Restore earlier removal")]
    )
    original = models.ForeignKey(
        "self", null=True, on_delete=models.PROTECT, related_name="restorations"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.CharField(max_length=500)
    fingerprint = models.CharField(max_length=64)
    details = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="credit_correction_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(kind="remove", original__isnull=True)
                | models.Q(kind="restore", original__isnull=False),
                name="credit_correction_original_scope",
            ),
        ]


class CustomerCreditCorrectionAllocation(FinancialFact):
    correction = models.ForeignKey(
        CustomerCreditCorrection, on_delete=models.PROTECT, related_name="allocations"
    )
    issue = models.ForeignKey(
        CustomerCreditIssue, on_delete=models.PROTECT, related_name="corrections"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["correction", "issue"], name="credit_correction_issue_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="credit_correction_allocation_positive"
            ),
        ]
