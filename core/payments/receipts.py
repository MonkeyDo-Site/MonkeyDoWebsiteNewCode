"""Actual manual receipt facts, separate from invoice and provider timestamps."""

from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.utils import timezone

from core.availability import NEW_YORK


def receipt_date(value=None):
    today = timezone.localdate(timezone=NEW_YORK)
    value = value or today
    if not isinstance(value, date) or isinstance(value, datetime) or value > today:
        raise ValidationError("Use the actual receipt date, no later than today.")
    return value


def sender(value, *, required=False):
    if not isinstance(value, str) or len(value) > 160:
        raise ValidationError("Enter the Zelle sender name/account, up to 160 characters.")
    value = value.strip()
    if required and not value:
        raise ValidationError("Enter the Zelle sender name/account shown by the bank.")
    return value
