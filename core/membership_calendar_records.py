"""Audited calendar corrections retain the original purchased M-numbered record."""

from django.conf import settings
from django.db import models

from .payments.models import FinancialFact


class MembershipCalendarCorrection(FinancialFact):
    id = models.UUIDField(primary_key=True, editable=False)
    purchase = models.ForeignKey(
        "core.MembershipPurchase", on_delete=models.PROTECT, related_name="calendar_corrections"
    )
    previous = models.OneToOneField(
        "self", null=True, on_delete=models.PROTECT, related_name="next_correction"
    )
    version = models.PositiveIntegerField()
    starts_on = models.DateField()
    ends_on = models.DateField()
    before = models.JSONField()
    cycles = models.JSONField()
    facts = models.JSONField()
    fingerprint = models.CharField(max_length=64)
    reason = models.TextField()
    customer_confirmed = models.BooleanField(default=False)
    send_confirmation = models.BooleanField(default=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["purchase", "version"], name="membership_calendar_one_version"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    version__gte=1, ends_on__gte=models.F("starts_on"), customer_confirmed=True
                ),
                name="membership_calendar_valid_correction",
            ),
        ]


class MembershipCalendarState(models.Model):
    """The current view points to evidence; original accepted dates are never updated."""

    purchase = models.OneToOneField(
        "core.MembershipPurchase",
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="calendar_state",
    )
    correction = models.OneToOneField(MembershipCalendarCorrection, on_delete=models.PROTECT)


class MembershipCalendarMessage(FinancialFact):
    correction = models.ForeignKey(
        MembershipCalendarCorrection, on_delete=models.PROTECT, related_name="messages"
    )
    message = models.OneToOneField("core.MessageDelivery", on_delete=models.PROTECT)
