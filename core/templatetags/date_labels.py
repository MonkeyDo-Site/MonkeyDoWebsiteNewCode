"""App-wide date rendering, including inherited staff/public/admin templates."""

from django import template

from core.date_display import display_date, display_time_range, weekday_name

register = template.Library()


@register.filter(name="date", expects_localtime=True)
def business_date(value, arg=None):
    return display_date(value, arg)


@register.filter
def weekday_label(value, style="full"):
    try:
        day = int(value)
        return weekday_name(day, short=style == "short") if 0 <= day <= 6 else ""
    except (ValueError, TypeError):
        return ""


@register.filter
def time_range(starts_at, ends_at):
    return display_time_range(starts_at, ends_at)
