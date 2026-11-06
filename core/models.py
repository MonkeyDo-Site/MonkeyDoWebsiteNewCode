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
