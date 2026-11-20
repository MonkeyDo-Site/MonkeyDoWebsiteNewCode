"""Versioned waiver metadata; completed signed documents live only in private R2."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from core.payments.models import FinancialFact


class WaiverVersion(FinancialFact):
    code = models.CharField(max_length=60, primary_key=True)
    legal_html = models.TextField()
    acknowledgments = models.JSONField()
    text_hash = models.CharField(max_length=64)
    source_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class WaiverSignature(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Evidence storage pending"
        SIGNED = "signed", "Signed"
        DELETING = "deleting", "Evidence removal pending"
        DELETED = "deleted", "Evidence removed under retention policy"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_key = models.UUIDField(unique=True)
    fingerprint = models.CharField(max_length=64)
    version = models.ForeignKey(WaiverVersion, on_delete=models.PROTECT)
    flow_hash = models.CharField(max_length=64, blank=True, db_index=True)
    signer_name = models.CharField(max_length=180)
    signer_email = models.EmailField(blank=True)
    signer_phone = models.CharField(max_length=30, blank=True)
    relationship = models.CharField(max_length=40)
    minors = models.JSONField(default=list, blank=True)
    signature_method = models.CharField(max_length=20, default="typed_legal_name", editable=False)
    adult_accepted = models.BooleanField()
    waiver_accepted = models.BooleanField()
    electronic_accepted = models.BooleanField()
    signed_at = models.DateTimeField()
    valid_until = models.DateTimeField()
    delete_after = models.DateTimeField(db_index=True)
    object_key = models.CharField(max_length=150, unique=True)
    evidence_hash = models.CharField(max_length=64)
    state = models.CharField(max_length=10, choices=State.choices, default=State.PENDING)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [("view_signed_waiver", "View private signed waiver evidence")]
        constraints = [
            models.CheckConstraint(
                condition=Q(adult_accepted=True, waiver_accepted=True, electronic_accepted=True),
                name="waiver_explicit_consents_required",
            )
        ]


class WaiverCustomerLink(FinancialFact):
    signature = models.ForeignKey(
        WaiverSignature, on_delete=models.PROTECT, related_name="customer_links"
    )
    customer = models.ForeignKey(
        "core.Customer", on_delete=models.PROTECT, related_name="waiver_links"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["signature", "customer"], name="waiver_customer_unique")
        ]


class WaiverBookingLink(FinancialFact):
    signature = models.ForeignKey(
        WaiverSignature, on_delete=models.PROTECT, related_name="booking_links"
    )
    booking = models.ForeignKey(
        "core.Booking", on_delete=models.PROTECT, related_name="waiver_links"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["signature", "booking"], name="waiver_booking_unique")
        ]


class WaiverShareLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        "core.Booking", on_delete=models.PROTECT, related_name="waiver_share_links"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    revoked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)


class BookingWaiverReview(models.Model):
    booking = models.OneToOneField(
        "core.Booking", on_delete=models.PROTECT, related_name="waiver_review"
    )
    coverage_confirmed = models.BooleanField(default=False)
    paper_signed = models.BooleanField(default=False)
    share_requested = models.BooleanField(default=False)
    # Owner/staff audit contains actors/times for actual paper/coverage confirmations.
    updated_at = models.DateTimeField(auto_now=True)
