import re
from datetime import datetime, time

from django import template
from django.utils.formats import time_format

register = template.Library()


@register.filter
def display_session_label(value, starts_at=None):
    """Format legacy clock text in labels without rewriting owner-stored labels."""

    if isinstance(starts_at, datetime):
        from django.utils import timezone

        starts_at = timezone.localtime(starts_at).time()

    def clock(match):
        hour, minute = int(match[1]), int(match[2])
        if hour <= 12 and starts_at is None:
            return match[0]  # An ambiguous owner label must never invent AM.
        if (
            starts_at is not None
            and hour % 12 == starts_at.hour % 12
            and minute == starts_at.minute
        ):
            return time_format(starts_at, "g:i A")
        return time_format(time(hour, minute), "g:i A")

    return re.sub(r"(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:]|\s*[APap][Mm])", clock, value)


@register.filter
def play_mode_label(value):
    return {
        "accompanied": "Open Play only",
        "supervised": "Supervised Play only",
        "both": "Open Play and Supervised Play",
    }.get(value, value)
