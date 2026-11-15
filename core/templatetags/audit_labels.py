from datetime import datetime

from django import template
from django.utils import timezone

from core.models import Session

register = template.Library()
LABELS = {
    "children": "Children",
    "referral_source": "Referral source",
    "adults": "Adults",
    "babies": "Babies",
    "socks": "Grip socks",
    "supervised": "Play type",
    "session_id": "Session",
    "expected_method": "Expected payment method",
    "attendance": "Status",
    "kind": "Membership type",
    "places": "Amount",
    "months": "Months",
    "billing": "Billing",
    "starts_on": "Start date",
    "ends_on": "End date",
}


def value(key, item, state=None):
    if key == "supervised":
        return "Supervised Play" if item else "Open Play"
    if key == "session_id" and item:
        if state and state.get("session_starts_at") and state.get("session_ends_at"):
            start = timezone.localtime(datetime.fromisoformat(state["session_starts_at"]))
            end = timezone.localtime(datetime.fromisoformat(state["session_ends_at"]))
            return f"{start:%b %d, %Y %I:%M %p}–{end:%I:%M %p}"
        row = Session.objects.filter(pk=item).first()
        if row:
            return f"{timezone.localtime(row.starts_at):%b %d, %Y %I:%M %p}–{timezone.localtime(row.ends_at):%I:%M %p}"
    return str(item).replace("_", " ").title() if isinstance(item, str) else item


@register.inclusion_tag("core/partials/audit_event.html")
def audit_event(event):
    data = event.changes
    before, after = data.get("before"), data.get("after")
    changes = []
    if isinstance(after, dict):
        before = before if isinstance(before, dict) else {}
        for key, new in after.items():
            if key in LABELS and before.get(key) != new:
                changes.append(
                    {
                        "label": LABELS[key],
                        "before": value(key, before[key], before) if key in before else "—",
                        "after": value(key, new, after),
                    }
                )
    elif event.action == "membership.draft_created":
        changes = [
            {"label": LABELS[key], "before": "—", "after": value(key, item)}
            for key, item in data.items()
            if key in LABELS
        ]
    actions = {
        "booking.updated": "Booking edited",
        "booking.attendees_changed": "Attendees changed",
        "booking.timing_changed": "Session changed",
        "booking.test_released": "Booking cancelled",
        "booking.test_created": "Booking created",
        "booking.customer_test_created": "Customer test booking created",
        "membership.draft_created": "Membership draft created",
    }
    return {
        "event": event,
        "action_label": actions.get(
            event.action, " ".join(event.action.split(".")[-1].split("_")).capitalize()
        ),
        "changes": changes,
    }
