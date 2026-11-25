"""Business weekday wording without changing civil dates, times or stored values."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from django.template.defaultfilters import date as django_date
from django.utils import timezone

NEW_YORK = ZoneInfo("America/New_York")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Motzei Shabbos", "Sunday")
SHORT_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Motzei Shabbos", "Sun")


def weekday_name(day, *, short=False):
    return (SHORT_WEEKDAYS if short else WEEKDAYS)[day]


def local_value(value):
    if isinstance(value, datetime) and timezone.is_aware(value):
        return timezone.localtime(value, NEW_YORK)
    return value


def weekday_wording(text, value):
    if hasattr(value, "weekday") and value.weekday() == 5:
        return re.sub(r"\b(?:Saturday|Sat)\b", "Motzei Shabbos", text)
    return text


def display_date(value, format_string=None):
    value = local_value(value)
    return weekday_wording(django_date(value, format_string), value)


def display_strftime(value, format_string):
    value = local_value(value)
    return weekday_wording(value.strftime(format_string), value)


def display_time_range(starts_at, ends_at):
    """Omit a repeated meridiem, using the business timezone for both endpoints."""
    start = local_value(starts_at)
    end = local_value(ends_at)
    start_format = "g:i" if (start.hour < 12) == (end.hour < 12) else "g:i A"
    return f"{display_date(start, start_format)}–{display_date(end, 'g:i A')}"
