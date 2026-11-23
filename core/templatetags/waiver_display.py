import re

from django import template

register = template.Library()


@register.filter
def display_name(value):
    """Display only; never rewrite signed evidence or customer names."""
    return (
        re.sub(r"\b([a-z])", lambda m: m.group(1).upper(), str(value))
        if str(value).islower()
        else value
    )


@register.filter
def display_names(names):
    return ", ".join(str(display_name(name)) for name in names)
