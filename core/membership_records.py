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

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source="staff", actor__isnull=False)
                | models.Q(source="public", actor__isnull=True),
                name="membership_purchase_source_actor",
            )
        ]

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


class MembershipRenewalLink(FinancialFact):
    """Signed private address; thirty-day validity never changes renewal grace."""

    id = models.UUIDField(primary_key=True, editable=False)
    prior = models.ForeignKey(
        MembershipPurchase, on_delete=models.PROTECT, related_name="renewal_links"
    )
    customer = models.ForeignKey("core.Customer", on_delete=models.PROTECT)
    expires_at = models.DateTimeField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class MembershipRenewalLinkRevocation(FinancialFact):
    link = models.OneToOneField(
        MembershipRenewalLink, primary_key=True, on_delete=models.PROTECT, related_name="revocation"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now_add=True)


class MembershipPublicAcceptance(FinancialFact):
    """Durable scope for the explicitly accepted first public renewal payment."""

    purchase = models.OneToOneField(
        MembershipPurchase,
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="public_acceptance",
    )
    link = models.OneToOneField(
        MembershipRenewalLink, on_delete=models.PROTECT, related_name="acceptance"
    )
    card_authorization = models.ForeignKey(
        "core.MembershipCardAuthorization", on_delete=models.PROTECT
    )
    proof_hash = models.CharField(max_length=64)
    customer_revision = models.PositiveIntegerField()
    verified_at = models.DateTimeField()
    accepted_at = models.DateTimeField(auto_now_add=True)


class MembershipCardAuthorization(FinancialFact):
    """Card-storage authorization scoped to one reviewed membership purchase."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    setup = models.OneToOneField(
        "core.PaymentSetup",
        null=True,
        on_delete=models.PROTECT,
        related_name="membership_authorization",
    )
    method = models.ForeignKey(
        "core.PaymentMethod",
        null=True,
        on_delete=models.PROTECT,
        related_name="membership_authorizations",
    )
    customer = models.ForeignKey("core.Customer", on_delete=models.PROTECT)
    request_key = models.UUIDField()
    flow_hash = models.CharField(max_length=64, db_index=True)
    offer_fingerprint = models.CharField(max_length=64)
    terms_text = models.TextField()
    storage_version = models.CharField(max_length=60)
    storage_text = models.TextField()
    retain = models.BooleanField(default=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    accepted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(setup__isnull=False, method__isnull=True)
                | models.Q(setup__isnull=True, method__isnull=False),
                name="membership_card_authority_source",
            )
        ]


class MembershipBillingAction(FinancialFact):
    """Accepted staff billing actions, independent of later provider outcomes."""

    id = models.UUIDField(primary_key=True, editable=False)
    purchase = models.ForeignKey(
        MembershipPurchase, on_delete=models.PROTECT, related_name="billing_actions"
    )
    kind = models.CharField(
        max_length=12, choices=[("payment", "Payment"), ("card_update", "Card update")]
    )
    fingerprint = models.CharField(max_length=64)
    details = models.JSONField()
    operation = models.OneToOneField(
        "core.PaymentOperation",
        null=True,
        on_delete=models.PROTECT,
        related_name="membership_billing_action",
    )
    mandate = models.OneToOneField(
        MembershipCardMandate,
        null=True,
        on_delete=models.PROTECT,
        related_name="billing_action",
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(kind="payment", operation__isnull=False, mandate__isnull=True)
                    | models.Q(kind="card_update", operation__isnull=True, mandate__isnull=False)
                ),
                name="membership_billing_action_evidence",
            )
        ]


class MembershipBenefitBatch(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    booking = models.ForeignKey(
        "core.Booking", on_delete=models.PROTECT, related_name="membership_benefit_batches"
    )
    quote = models.ForeignKey("core.BookingQuote", null=True, on_delete=models.PROTECT)
    action = models.CharField(
        max_length=10, choices=[(x, x.title()) for x in ("reserved", "used", "released")]
    )
    fingerprint = models.CharField(max_length=64)
    reason = models.CharField(max_length=30)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now_add=True)


class MembershipBenefitAssignment(FinancialFact):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        "core.Booking", on_delete=models.PROTECT, related_name="membership_benefits"
    )
    quote = models.ForeignKey(
        "core.BookingQuote", on_delete=models.PROTECT, related_name="membership_benefits"
    )
    purchase = models.ForeignKey(
        MembershipPurchase, on_delete=models.PROTECT, related_name="benefit_assignments"
    )
    place = models.PositiveIntegerField()
    kind = models.CharField(
        max_length=30,
        choices=[
            (x, x.replace("_", " ").title())
            for x in (
                "unlimited_daily",
                "subscription_free",
                "subscription_additional",
                "subscription_supervised",
            )
        ],
    )
    appointment_on = models.DateField()
    cycle = models.ForeignKey("core.MembershipDraftCycle", on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=9, decimal_places=2)
    rules_version = models.CharField(max_length=60)
    reserved_by = models.ForeignKey(
        MembershipBenefitBatch, on_delete=models.PROTECT, related_name="assignments"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["quote", "purchase", "place"], name="membership_benefit_unique_place"
            )
        ]


class MembershipBenefitEvent(FinancialFact):
    assignment = models.ForeignKey(
        MembershipBenefitAssignment, on_delete=models.PROTECT, related_name="events"
    )
    batch = models.ForeignKey(
        MembershipBenefitBatch, on_delete=models.PROTECT, related_name="events"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "batch"], name="membership_benefit_unique_event"
            )
        ]


class MembershipBenefitState(models.Model):
    assignment = models.OneToOneField(
        MembershipBenefitAssignment,
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="current",
    )
    status = models.CharField(
        max_length=10, choices=[(x, x.title()) for x in ("reserved", "used", "released")]
    )
    event = models.OneToOneField(MembershipBenefitEvent, on_delete=models.PROTECT)


class MembershipOrigin(FinancialFact):
    """An explicit follow-on cohort never edits the membership it follows."""

    purchase = models.OneToOneField(
        MembershipPurchase, primary_key=True, on_delete=models.PROTECT, related_name="origin"
    )
    prior = models.ForeignKey(
        MembershipPurchase, on_delete=models.PROTECT, related_name="follow_on"
    )
    operation = models.CharField(
        max_length=10, choices=[("renewal", "Renewal"), ("addition", "Additional places")]
    )
    places = models.PositiveIntegerField()
    prior_ends_on = models.DateField()
    purchased_on = models.DateField()
    minimum_months = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(places__gte=1, minimum_months__gte=1),
                name="membership_origin_valid_amounts",
            ),
            models.CheckConstraint(
                condition=~models.Q(purchase=models.F("prior")),
                name="membership_origin_distinct_cohort",
            ),
        ]
