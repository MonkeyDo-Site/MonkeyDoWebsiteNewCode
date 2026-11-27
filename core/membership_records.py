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
        permissions = [("export_membership_records", "Export membership records")]
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
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    notice = models.OneToOneField(
        "core.MembershipRenewalNotice",
        null=True,
        on_delete=models.PROTECT,
        related_name="renewal_link",
    )
    prompt = models.OneToOneField(
        "core.MembershipPromptLink", null=True, on_delete=models.PROTECT, related_name="link"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(actor__isnull=False, notice__isnull=True, prompt__isnull=True)
                | models.Q(actor__isnull=True, notice__isnull=False, prompt__isnull=True)
                | models.Q(actor__isnull=True, notice__isnull=True, prompt__isnull=False),
                name="membership_renewal_link_authority",
            )
        ]


class MembershipRenewalPrompt(FinancialFact):
    """A displayed booking opportunity and the customer's explicit response."""

    id = models.UUIDField(primary_key=True, editable=False)
    purchase = models.ForeignKey(
        MembershipPurchase, on_delete=models.PROTECT, related_name="renewal_prompts"
    )
    customer = models.ForeignKey("core.Customer", on_delete=models.PROTECT)
    flow_key = models.UUIDField()
    source = models.CharField(max_length=6, choices=[("staff", "Staff"), ("public", "Customer")])
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    customer_revision = models.PositiveIntegerField()
    provenance = models.CharField(max_length=64)
    window = models.CharField(
        max_length=8, choices=[("initial", "Initial"), ("followup", "One later booking")]
    )
    action = models.CharField(
        max_length=11,
        choices=[
            (value, value.replace("_", " ").title())
            for value in ("seen", "renew", "not_now", "email_later")
        ],
    )
    ends_on = models.DateField()
    on = models.DateField()
    remind_at = models.DateTimeField(null=True, db_index=True)
    snapshot = models.JSONField()
    fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source="staff", actor__isnull=False)
                | models.Q(source="public", actor__isnull=True),
                name="membership_prompt_source_actor",
            ),
            models.CheckConstraint(
                condition=models.Q(action="email_later", remind_at__isnull=False)
                | (~models.Q(action="email_later") & models.Q(remind_at__isnull=True)),
                name="membership_prompt_reminder_scope",
            ),
            models.UniqueConstraint(
                fields=["purchase", "flow_key", "ends_on", "window", "action"],
                name="membership_prompt_action_once",
            ),
            models.UniqueConstraint(
                fields=["purchase", "flow_key", "ends_on", "window"],
                condition=~models.Q(action="seen"),
                name="membership_prompt_choice_once",
            ),
            models.UniqueConstraint(
                fields=["purchase", "ends_on"],
                condition=models.Q(window="followup", action="seen"),
                name="membership_prompt_one_followup",
            ),
        ]


class MembershipPromptLink(FinancialFact):
    """System authority for a chosen renewal or a due, requested reminder."""

    id = models.UUIDField(primary_key=True, editable=False)
    prompt = models.OneToOneField(
        MembershipRenewalPrompt, on_delete=models.PROTECT, related_name="link_authority"
    )
    created_at = models.DateTimeField(auto_now_add=True)


class MembershipPromptEmail(FinancialFact):
    authority = models.ForeignKey(
        MembershipPromptLink, on_delete=models.PROTECT, related_name="deliveries"
    )
    message = models.OneToOneField(
        "core.MessageDelivery", on_delete=models.PROTECT, related_name="renewal_prompt_evidence"
    )


class MembershipRenewalNotice(FinancialFact):
    """A system notice has its own authority, rather than a pretend staff actor."""

    id = models.UUIDField(primary_key=True, editable=False)
    purchase = models.ForeignKey(
        MembershipPurchase, on_delete=models.PROTECT, related_name="renewal_notices"
    )
    kind = models.CharField(
        max_length=6,
        choices=[("expiry", "Five days before expiry"), ("grace", "One day before grace ends")],
    )
    ends_on = models.DateField()
    due_on = models.DateField(db_index=True)
    places = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["purchase", "kind", "ends_on"], name="membership_notice_once_per_term"
            ),
            models.CheckConstraint(
                condition=models.Q(places__gt=0), name="membership_notice_positive_places"
            ),
        ]


class MembershipRenewalNoticeDelivery(FinancialFact):
    notice = models.ForeignKey(
        MembershipRenewalNotice, on_delete=models.PROTECT, related_name="deliveries"
    )
    message = models.OneToOneField(
        "core.MessageDelivery", on_delete=models.PROTECT, related_name="renewal_notice_evidence"
    )


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


class MembershipCancellation(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    purchase = models.ForeignKey(
        MembershipPurchase, on_delete=models.PROTECT, related_name="cancellations"
    )
    stopped_on = models.DateField()
    timing = models.CharField(
        max_length=12, choices=[("immediate", "Immediate"), ("end_cycle", "End of current cycle")]
    )
    early_override = models.BooleanField(default=False)
    reason = models.CharField(max_length=500)
    refund_amount = models.DecimalField(max_digits=14, decimal_places=2)
    fingerprint = models.CharField(max_length=64)
    snapshot = models.JSONField()
    send_confirmation = models.BooleanField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(refund_amount__gte=0),
                name="membership_cancel_nonnegative_refund",
            )
        ]


class MembershipRefundPlan(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    cancellation = models.ForeignKey(
        MembershipCancellation, on_delete=models.PROTECT, related_name="refund_plans"
    )
    original = models.ForeignKey(
        "core.PaymentOperation", on_delete=models.PROTECT, related_name="membership_refund_plans"
    )
    allocation = models.JSONField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="membership_refund_plan_positive"
            )
        ]


class MembershipRefundAttempt(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    plan = models.ForeignKey(
        MembershipRefundPlan, on_delete=models.PROTECT, related_name="attempts"
    )
    operation = models.OneToOneField(
        "core.PaymentOperation", on_delete=models.PROTECT, related_name="membership_refund_attempt"
    )
    fingerprint = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class MembershipBookingDecision(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    booking = models.ForeignKey(
        "core.Booking", on_delete=models.PROTECT, related_name="membership_decisions"
    )
    session = models.ForeignKey("core.Session", on_delete=models.PROTECT)
    mode = models.CharField(
        max_length=10, choices=[(x, x.title()) for x in ("normal", "ordinary", "honor")]
    )
    memberships = models.JSONField(default=list)
    reason = models.CharField(max_length=240)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


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
