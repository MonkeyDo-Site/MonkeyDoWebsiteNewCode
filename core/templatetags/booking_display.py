"""Display-only public contact and quantity formatting."""

import re

from django import template

register = template.Library()


@register.filter
def phone_display(value):
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}" if len(digits) == 10 else value


@register.filter
def count_words(value, kind):
    words = {
        "child": ("child", "children"),
        "adult": ("adult", "adults"),
        "baby": ("baby", "babies"),
        "socks": ("pair of socks", "pairs of socks"),
    }
    singular, plural = words[kind]
    return f"{value} {singular if value == 1 else plural}"
