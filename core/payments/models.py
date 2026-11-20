"""Payment foundation. No raw card fields; immutable financial facts are append-only."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class FinancialQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Accepted financial facts cannot be rewritten.")

    def delete(self):
        raise ValidationError("Accepted financial facts cannot be deleted.")


class FinancialFact(models.Model):
    objects = FinancialQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Accepted financial facts cannot be rewritten.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Accepted financial facts cannot be deleted.")


class PaymentMethod(models.Model):
    class State(models.TextChoices):
        ACTIVE = "active", "Available"
        REMOVING = "removing", "Removal pending"
        REMOVED = "removed", "Removed"
        UNKNOWN = "unknown", "Review required"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey("core.Customer", null=True, on_delete=models.PROTECT)
    booking = models.ForeignKey("core.Booking", null=True, on_delete=models.PROTECT)
    # References are private charging sources, never public display/export values.
    provider_customer = models.CharField(max_length=40)
    provider_method = models.CharField(max_length=40, null=True, unique=True)
    environment = models.CharField(max_length=8, default="sandbox", editable=False)
    brand = models.CharField(max_length=30)
    last_four = models.CharField(max_length=4)
    reusable = models.BooleanField(default=False)
    consent_version = models.CharField(max_length=60)
    consent_at = models.DateTimeField()
    state = models.CharField(max_length=10, choices=State.choices, default=State.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(environment="sandbox"), name="method_sandbox_only")
        ]

    def __str__(self):
        return f"Saved payment method ending in {self.last_four}"


class FinancialSale(FinancialFact):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creation_key = models.UUIDField(unique=True)
    fingerprint = models.CharField(max_length=64)
    customer = models.ForeignKey("core.Customer", on_delete=models.PROTECT)
    booking = models.ForeignKey("core.Booking", null=True, on_delete=models.PROTECT)
    quote = models.ForeignKey("core.BookingQuote", null=True, on_delete=models.PROTECT)
    kind = models.CharField(
        max_length=20,
        default="visit",
        choices=[
            (x, x.replace("_", " ").title())
            for x in ("visit", "cancellation", "partial_fee", "adjustment")
        ],
    )
    booking_version = models.PositiveIntegerField(default=1)
    environment = models.CharField(max_length=8, default="sandbox", editable=False)
    currency = models.CharField(max_length=3, default="USD", editable=False)
    customer_label = models.CharField(max_length=120)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    processing_fee = models.DecimalField(max_digits=14, decimal_places=2)
    sales_tax = models.DecimalField(max_digits=14, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=7, decimal_places=6)
    fee_rate = models.DecimalField(max_digits=7, decimal_places=6)
    policy_id_at_sale = models.PositiveBigIntegerField()
    service_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)

    class Meta:
        permissions = [
            ("collect_payment", "Collect or record approved payments"),
            ("review_payment", "Review payment issues and reconciliation"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(environment="sandbox", currency="USD"), name="sale_sandbox_usd_only"
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0, processing_fee__gte=0, sales_tax__gte=0, total__gte=0),
                name="sale_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(
                    total=models.F("subtotal") + models.F("processing_fee") + models.F("sales_tax")
                ),
                name="sale_total_reconciles",
            ),
        ]


class FinancialLine(FinancialFact):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(FinancialSale, on_delete=models.PROTECT, related_name="lines")
    position = models.PositiveSmallIntegerField()
    category = models.CharField(max_length=40)
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    net = models.DecimalField(max_digits=14, decimal_places=2)
    taxable = models.BooleanField()
    fee = models.DecimalField(max_digits=14, decimal_places=2)
    item_tax = models.DecimalField(max_digits=14, decimal_places=2)
    fee_tax = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["sale", "position"], name="sale_line_position_unique"),
            models.CheckConstraint(
                condition=Q(
                    unit_price__gte=0, net__gte=0, fee__gte=0, item_tax__gte=0, fee_tax__gte=0
                ),
                name="financial_line_nonnegative",
            ),
        ]


class PaymentOperation(models.Model):
    class State(models.TextChoices):
        READY = "ready", "Ready"
        SENDING = "sending", "Processing"
        UNKNOWN = "unknown", "Outcome unknown"
        SUCCEEDED = "succeeded", "Succeeded"
        DECLINED = "declined", "Declined"
        ACTION = "action", "Authentication or review required"
        CANCELLED = "cancelled", "Cancelled before sending"

    class Kind(models.TextChoices):
        RECEIPT = "receipt", "Payment"
        REFUND = "refund", "Refund"
        VOID = "void", "Void"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_key = models.UUIDField(unique=True)
    fingerprint = models.CharField(max_length=64)
    sale = models.ForeignKey(FinancialSale, on_delete=models.PROTECT, related_name="operations")
    original = models.ForeignKey(
        "self", null=True, on_delete=models.PROTECT, related_name="adjustments"
    )
    method = models.ForeignKey(PaymentMethod, null=True, on_delete=models.PROTECT)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    tender = models.CharField(
        max_length=12,
        choices=[(x, x.title()) for x in ("card", "cash", "check", "zelle", "gift_card")],
    )
    brand = models.CharField(max_length=30, blank=True)
    last_four = models.CharField(max_length=4, blank=True)
    purpose = models.CharField(
        max_length=20,
        default="arrival",
        choices=[
            (x, x.replace("_", " ").title())
            for x in ("arrival", "cancellation", "no_show", "correction")
        ],
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    allocation = models.JSONField()
    state = models.CharField(max_length=10, choices=State.choices, default=State.READY)
    provider_reference = models.CharField(max_length=40, blank=True)
    # Only approved, normalized classifications; never raw provider response text.
    result_code = models.CharField(max_length=40, blank=True)
    reconciliation_required = models.BooleanField(default=False)
    requested_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="operation_amount_positive"),
            models.CheckConstraint(
                condition=(
                    Q(kind="receipt", original__isnull=True)
                    | Q(kind__in=["refund", "void"], original__isnull=False)
                ),
                name="operation_original_required",
            ),
            models.UniqueConstraint(
                fields=["kind", "provider_reference"],
                condition=~Q(provider_reference=""),
                name="operation_provider_reference_unique",
            ),
        ]


class FinancialPosting(FinancialFact):
    operation = models.ForeignKey(
        PaymentOperation, on_delete=models.PROTECT, related_name="postings"
    )
    line = models.ForeignKey(FinancialLine, on_delete=models.PROTECT, related_name="postings")
    net = models.DecimalField(max_digits=14, decimal_places=2)
    fee = models.DecimalField(max_digits=14, decimal_places=2)
    item_tax = models.DecimalField(max_digits=14, decimal_places=2)
    fee_tax = models.DecimalField(max_digits=14, decimal_places=2)
    occurred_at = models.DateTimeField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["operation", "line"], name="posting_operation_line_unique"
            ),
            models.CheckConstraint(
                condition=Q(net__gte=0, fee__gte=0, item_tax__gte=0, fee_tax__gte=0),
                name="posting_components_nonnegative",
            ),
        ]


class PaymentEvent(FinancialFact):
    operation = models.ForeignKey(PaymentOperation, on_delete=models.PROTECT, related_name="events")
    state = models.CharField(max_length=10)
    source = models.CharField(max_length=20)
    code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)

    @property
    def state_label(self):
        return dict(PaymentOperation.State.choices).get(self.state, "Review required")


class ProviderEvent(FinancialFact):
    event_id = models.CharField(max_length=200, unique=True)
    payload_hash = models.CharField(max_length=64)
    event_type = models.CharField(max_length=80)
    provider_reference = models.CharField(max_length=40, blank=True)
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    # Persist a bounded allowlist only, not arbitrary webhook/card/customer data.
    facts = models.JSONField(default=dict)


class DurableJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=200, unique=True)
    kind = models.CharField(max_length=40)
    reference = models.CharField(max_length=200)
    state = models.CharField(
        max_length=10,
        default="queued",
        choices=[(x, x.title()) for x in ("queued", "running", "done", "blocked")],
    )
    available_at = models.DateTimeField()
    lease_until = models.DateTimeField(null=True)
    lease_token = models.UUIDField(null=True)
    attempts = models.PositiveIntegerField(default=0)
    code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["state", "available_at"], name="job_ready_idx")]


class ProviderObservation(FinancialFact):
    operation = models.ForeignKey(
        PaymentOperation, on_delete=models.PROTECT, related_name="observations"
    )
    fingerprint = models.CharField(max_length=64)
    provider_reference = models.CharField(max_length=40)
    provider_status = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    occurred_at = models.DateTimeField(null=True)
    settled_date = models.DateField(null=True)
    batch_reference = models.CharField(max_length=40, blank=True)
    brand = models.CharField(max_length=30, blank=True)
    last_four = models.CharField(max_length=4, blank=True)
    observed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["operation", "fingerprint"], name="provider_observation_unique"
            )
        ]


class PaymentSetup(models.Model):
    """One durable claim for a transient nonce exchange; the nonce is never saved."""

    id = models.UUIDField(primary_key=True, editable=False)
    flow_hash = models.CharField(max_length=64, db_index=True)
    nonce_hash = models.CharField(max_length=64)
    customer = models.ForeignKey("core.Customer", null=True, on_delete=models.PROTECT)
    customer_revision = models.PositiveIntegerField(null=True)
    provider_customer = models.CharField(max_length=40, blank=True)
    method = models.OneToOneField(PaymentMethod, null=True, on_delete=models.PROTECT)
    consent = models.OneToOneField(
        "core.PaymentConsent", null=True, on_delete=models.PROTECT, related_name="+"
    )
    reusable = models.BooleanField(default=False)
    state = models.CharField(
        max_length=20,
        default="prepared",
        choices=[
            (x, x.replace("_", " ").title())
            for x in (
                "prepared",
                "customer_sending",
                "method_sending",
                "succeeded",
                "unknown",
                "failed",
            )
        ],
    )
    code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)


class PaymentPolicyVersion(FinancialFact):
    version = models.CharField(max_length=60, primary_key=True)
    content_hash = models.CharField(max_length=64)
    text = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class PaymentConsent(FinancialFact):
    policy = models.ForeignKey(PaymentPolicyVersion, on_delete=models.PROTECT)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT, related_name="consents")
    flow_hash = models.CharField(max_length=64, db_index=True)
    version = models.CharField(max_length=60)
    policy_hash = models.CharField(max_length=64)
    payment_accepted = models.BooleanField()
    cancellation_accepted = models.BooleanField()
    future_use_accepted = models.BooleanField(default=False)
    source = models.CharField(max_length=8, choices=[("public", "Public"), ("staff", "Staff")])
    accepted_at = models.DateTimeField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(payment_accepted=True, cancellation_accepted=True),
                name="payment_consents_required",
            )
        ]


class BookingCardAgreement(models.Model):
    booking = models.OneToOneField(
        "core.Booking", on_delete=models.PROTECT, related_name="card_agreement"
    )
    method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT, related_name="agreements")
    consent = models.OneToOneField(PaymentConsent, on_delete=models.PROTECT)
    resolved_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
