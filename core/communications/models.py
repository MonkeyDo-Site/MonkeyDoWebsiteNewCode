import uuid

from django.conf import settings
from django.db import models

from core.payments.models import FinancialFact


class MessageDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dedupe_key = models.CharField(max_length=200, unique=True)
    fingerprint = models.CharField(max_length=64)
    customer = models.ForeignKey(
        "core.Customer", null=True, on_delete=models.PROTECT, related_name="messages"
    )
    booking = models.ForeignKey(
        "core.Booking", null=True, on_delete=models.PROTECT, related_name="messages"
    )
    kind = models.CharField(
        max_length=40,
        choices=[
            ("booking_confirmation", "Booking Confirmation"),
            ("booking_waiver", "Booking Confirmation with Waiver Link"),
            ("waiver_completed", "Waiver Completed Notification"),
            ("payment_issue", "Owner Payment Alert"),
        ],
    )
    template_version = models.CharField(max_length=60)
    recipient = models.EmailField()
    subject = models.CharField(max_length=200)
    text_body = models.TextField()
    unsigned_waiver = models.BooleanField(default=False)
    state = models.CharField(
        max_length=12,
        default="queued",
        choices=[
            (x, label)
            for x, label in (
                ("queued", "Queued"),
                ("sending", "Sending"),
                ("sent", "Sent to email provider"),
                ("unknown", "Delivery outcome unknown"),
                ("failed", "Sending failed"),
                ("cancelled", "Superseded before sending"),
            )
        ],
    )
    provider_reference = models.CharField(max_length=80, blank=True)
    code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True)
    sent_at = models.DateTimeField(null=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)


class MessageEvent(FinancialFact):
    delivery = models.ForeignKey(MessageDelivery, on_delete=models.PROTECT, related_name="events")
    state = models.CharField(max_length=12)
    code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
