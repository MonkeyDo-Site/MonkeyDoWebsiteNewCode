import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q


class Customer(models.Model):
    revision = models.PositiveIntegerField(default=1)
    # Database sequence provides never-reused identifiers on PostgreSQL; records are protected.
    last_name = models.CharField(max_length=120)
    phone = models.CharField(
        max_length=10,
        unique=True,
        validators=[RegexValidator(r"^\d{10}$", "Use a ten-digit US phone number.")],
    )
    email = models.EmailField()
    previous_phone = models.CharField(max_length=10, blank=True)
    previous_email = models.EmailField(blank=True)
    customer_type = models.CharField(
        max_length=10, choices=[("family", "Family"), ("day_camp", "Day Camp")], default="family"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [("view_customer_history", "View customer correction history")]
        constraints = [
            models.CheckConstraint(
                condition=Q(phone__regex=r"^[0-9]{10}$"), name="customer_phone_normalized"
            ),
            models.CheckConstraint(
                condition=Q(previous_phone="") | Q(previous_phone__regex=r"^[0-9]{10}$"),
                name="customer_previous_phone_normalized",
            ),
            models.CheckConstraint(condition=Q(revision__gte=1), name="customer_revision_positive"),
        ]

    @property
    def customer_number(self):
        return f"{self.pk:06d}"

    def __str__(self):
        return f"{self.customer_number} · {self.last_name}"


class SiteSettings(models.Model):
    staging_password_hash = models.CharField(max_length=128, blank=True, editable=False)
    staging_password_changed_at = models.DateTimeField(null=True, editable=False)
    staging_access_version = models.UUIDField(default=uuid.uuid4, editable=False)
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    booking_horizon_days = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    clubs_visible = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name="settings_singleton"),
            models.CheckConstraint(
                condition=Q(booking_horizon_days__gte=1, booking_horizon_days__lte=10),
                name="settings_horizon_range",
            ),
        ]

    def clean(self):
        if self.pk != 1:
            raise ValidationError("Only one site settings record is allowed.")


class Session(models.Model):
    class Kind(models.TextChoices):
        ORDINARY = "ordinary", "Ordinary play"
        PARTY = "party", "Party"
        EXCLUSIVE = "exclusive", "Exclusive group"

    revision = models.PositiveIntegerField(default=1)
    play_mode = models.CharField(
        max_length=12,
        choices=[
            ("both", "Accompanied and supervised"),
            ("accompanied", "Accompanied only"),
            ("supervised", "Supervised only"),
        ],
        default="both",
    )
    starts_at = models.DateTimeField(unique=True)
    ends_at = models.DateTimeField()
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.ORDINARY)
    public = models.BooleanField(default=False)
    closed = models.BooleanField(default=False)
    private_label = models.CharField(max_length=120, blank=True)
    child_capacity = models.PositiveSmallIntegerField(default=35)
    total_capacity = models.PositiveSmallIntegerField(default=50)
    supervised_capacity = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="session_end_after_start"
            ),
            models.CheckConstraint(
                condition=Q(supervised_capacity__lte=F("child_capacity")),
                name="supervised_within_child_capacity",
            ),
            models.CheckConstraint(
                condition=Q(child_capacity__lte=F("total_capacity")),
                name="child_within_total_capacity",
            ),
        ]

    def __str__(self):
        from django.utils import timezone

        return timezone.localtime(self.starts_at).strftime("%a %b %d, %Y %I:%M %p")


class Booking(models.Model):
    class Attendance(models.TextChoices):
        ARRIVED = "arrived", "Arrived"
        NO_SHOW = "no_show", "No show"
        CANCELLED = "cancelled", "Cancelled"

    creation_actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.PROTECT,
        related_name="created_bookings",
    )
    edit_version = models.PositiveIntegerField(default=1)
    socks = models.PositiveIntegerField(default=0)
    expected_method = models.CharField(
        max_length=12,
        choices=[
            ("card", "Credit card"),
            ("cash", "Cash"),
            ("check", "Check"),
            ("zelle", "Zelle"),
            ("gift_card", "Gift card"),
        ],
        default="card",
    )
    setup_pending = models.BooleanField(default=True)
    creation_key = models.UUIDField(null=True, unique=True, editable=False)
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="bookings")
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name="bookings")
    children = models.PositiveSmallIntegerField(default=0)
    adults = models.PositiveSmallIntegerField(default=1)
    babies = models.PositiveSmallIntegerField(default=0)
    supervised = models.BooleanField(default=False)
    attendance = models.CharField(max_length=12, choices=Attendance.choices, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(children__gt=0) | Q(adults__gt=0) | Q(babies__gt=0),
                name="booking_has_attendee",
            ),
            models.CheckConstraint(
                condition=Q(supervised=False, adults__gte=1)
                | Q(supervised=True, children__gte=1, adults=0, babies=0),
                name="booking_mode_attendees",
            ),
        ]

    @property
    def status_label(self):
        if self.setup_pending and self.attendance == self.Attendance.CANCELLED:
            return "Released test reservation"
        if self.setup_pending and not self.attendance:
            return "Setup pending"
        return self.get_attendance_display() or "Upcoming"


class AuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Audit events are append-only.")

    def delete(self):
        raise ValidationError("Audit events are append-only.")


class AuditEvent(models.Model):
    objects = AuditQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Audit events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events are append-only.")

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    record_type = models.CharField(max_length=80)
    record_id = models.CharField(max_length=80)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class CustomerComment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField(max_length=4000)
    search_digits = models.CharField(max_length=4000, blank=True, editable=False)
    system_generated = models.BooleanField(default=False, editable=False)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class LoginThrottle(models.Model):
    key = models.CharField(max_length=80, unique=True)
    failures = models.PositiveIntegerField(default=0)
    last_failure = models.DateTimeField(null=True)
    blocked_until = models.DateTimeField(null=True)


class SecurityAlert(models.Model):
    subject = models.CharField(max_length=160)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-created_at"]


class AccountSecurity(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="account_security"
    )
    version = models.PositiveIntegerField(default=1)
    secondary_email = models.EmailField(blank=True)


class OwnerChallenge(models.Model):
    delivered = models.BooleanField(default=False)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    digest = models.CharField(max_length=64)
    credential_hash = models.CharField(max_length=64)
    version = models.PositiveIntegerField()
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True)
    last_sent_at = models.DateTimeField()


class TrustedOwnerBrowser(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    digest = models.CharField(max_length=64, unique=True)
    version = models.PositiveIntegerField()
    expires_at = models.DateTimeField()


class OwnerRecoveryCode(models.Model):
    retired_at = models.DateTimeField(null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    digest = models.CharField(max_length=64, unique=True)
    used_at = models.DateTimeField(null=True)


class SecurityRequestLimit(models.Model):
    key = models.CharField(max_length=80, unique=True)
    started_at = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)


class PriceRecordQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Historical pricing records are immutable.")

    def delete(self):
        raise ValidationError("Historical pricing records are immutable.")


class ImmutablePriceRecord(models.Model):
    objects = PriceRecordQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Historical pricing records are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Historical pricing records are immutable.")


class PricingPolicy(ImmutablePriceRecord):
    child_price = models.DecimalField(
        max_digits=9, decimal_places=2, default="15.00", validators=[MinValueValidator(0)]
    )
    extra_adult_price = models.DecimalField(
        max_digits=9, decimal_places=2, default="5.00", validators=[MinValueValidator(0)]
    )
    minimum_admission = models.DecimalField(
        max_digits=9, decimal_places=2, default="15.00", validators=[MinValueValidator(0)]
    )
    supervised_price = models.DecimalField(
        max_digits=9, decimal_places=2, default="18.99", validators=[MinValueValidator(0)]
    )
    sock_price = models.DecimalField(
        max_digits=9, decimal_places=2, default="1.99", validators=[MinValueValidator(0)]
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default="0.0660",
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    card_fee_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default="0.0300",
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    tax_rate__gte=0,
                    tax_rate__lte=1,
                    card_fee_rate__gte=0,
                    card_fee_rate__lte=1,
                    child_price__gte=0,
                    extra_adult_price__gte=0,
                    minimum_admission__gte=0,
                    supervised_price__gte=0,
                    sock_price__gte=0,
                ),
                name="pricing_policy_valid_amounts",
            )
        ]


class BookingQuote(ImmutablePriceRecord):
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="quotes")
    policy = models.ForeignKey(PricingPolicy, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    snapshot = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "revision"], name="booking_quote_unique_revision"
            )
        ]


class CalendarDate(models.Model):
    day = models.DateField(unique=True)
    closed = models.BooleanField(default=False)
    private_reason = models.CharField(max_length=500, blank=True)
    chol_hamoed = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["day"]


class MembershipPricing(ImmutablePriceRecord):
    subscription = models.DecimalField(
        max_digits=9, decimal_places=2, default="17.99", validators=[MinValueValidator(0)]
    )
    unlimited = models.DecimalField(
        max_digits=9, decimal_places=2, default="39.99", validators=[MinValueValidator(0)]
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(subscription__gte=0, unlimited__gte=0),
                name="membership_prices_nonnegative",
            )
        ]


class MembershipDraft(ImmutablePriceRecord):
    customer = models.ForeignKey(
        Customer, related_name="membership_drafts", on_delete=models.PROTECT
    )
    kind = models.CharField(
        max_length=12, choices=[("subscription", "Subscription"), ("unlimited", "Unlimited")]
    )
    places = models.PositiveIntegerField()
    months = models.PositiveIntegerField()
    billing = models.CharField(
        max_length=12, choices=[("monthly", "Monthly"), ("prepaid", "Prepaid")]
    )
    starts_on = models.DateField()
    ends_on = models.DateField()
    unit_price = models.DecimalField(max_digits=9, decimal_places=2)
    pricing = models.ForeignKey(MembershipPricing, on_delete=models.PROTECT)
    fee_policy = models.ForeignKey(PricingPolicy, on_delete=models.PROTECT)
    expected_method = models.CharField(
        max_length=12,
        choices=[
            ("card", "Credit card"),
            ("cash", "Cash"),
            ("check", "Check"),
            ("zelle", "Zelle"),
            ("gift_card", "Gift card"),
        ],
    )
    snapshot = models.JSONField()
    creation_key = models.UUIDField(unique=True, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    places__gte=1, months__gte=3, ends_on__gte=F("starts_on"), unit_price__gte=0
                ),
                name="membership_draft_valid_term",
            )
        ]


class MembershipDraftCycle(ImmutablePriceRecord):
    draft = models.ForeignKey(MembershipDraft, related_name="cycles", on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    starts_on = models.DateField()
    ends_on = models.DateField()
    charge_on = models.DateField(null=True)
    quote = models.JSONField(null=True)

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(
                fields=["draft", "number"], name="membership_draft_unique_cycle"
            ),
            models.CheckConstraint(
                condition=Q(number__gte=1, ends_on__gte=F("starts_on")),
                name="membership_draft_cycle_valid_bounds",
            ),
        ]
