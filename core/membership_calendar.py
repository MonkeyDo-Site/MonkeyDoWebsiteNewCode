"""New York civil-date membership rules. No payment or benefit activation."""

from calendar import monthrange
from datetime import date, timedelta

from django.core.exceptions import ValidationError


def boundary(start, offset):
    if type(start) is not date or type(offset) is not int or offset < 0:
        raise ValidationError("Use a civil start date and nonnegative month offset.")
    month_index = start.year * 12 + start.month - 1 + offset
    year, month = divmod(month_index, 12)
    month += 1
    if not 1 <= year <= 9999:
        raise ValidationError("Term exceeds the supported calendar date range.")
    last = monthrange(year, month)[1]
    charged = date(year, month, min(start.day, last))
    try:
        reset = charged if start.day <= last else charged + timedelta(days=1)
    except OverflowError:
        raise ValidationError("Term exceeds the supported calendar date range.") from None
    return charged, reset


def schedule(start, months):
    if type(months) is not int or months < 1:
        raise ValidationError("Choose a positive whole number of months.")
    # Check the complete term before allocating any cycle rows.
    boundary(start, months)
    rows = []
    for index in range(months):
        charged, reset = boundary(start, index)
        _, next_reset = boundary(start, index + 1)
        rows.append(
            {
                "number": index + 1,
                "starts_on": reset,
                "ends_on": next_reset - timedelta(days=1),
                "charge_on": charged,
            }
        )
    return rows


def renewal_start(expiry, renewed_on):
    if type(expiry) is not date or type(renewed_on) is not date:
        raise ValidationError("Use civil dates for renewal review.")
    try:
        return max(expiry + timedelta(days=1), renewed_on), (
            1 if renewed_on <= expiry + timedelta(days=7) else 3
        )
    except OverflowError:
        raise ValidationError("Renewal exceeds the supported calendar date range.") from None
