import re
from datetime import time

from django import template
from django.utils.formats import time_format

register = template.Library()


@register.filter
def display_session_label(value):
    """Format legacy clock text in labels without rewriting owner-stored labels."""
    return re.sub(
        r"(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:]|\s*[APap][Mm])",
        lambda match: time_format(time(int(match[1]), int(match[2])), "g:i A"),
        value,
    )
