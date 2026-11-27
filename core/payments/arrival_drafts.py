"""Private, expiring arrival drafts. Saving a draft never records attendance or money."""

import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

KEY = "arrival_review_drafts"
FIELDS = (
    "pending_review",
    "pending_reason",
    "request_key",
    "version",
    "children",
    "adults",
    "babies",
    "socks",
    "method",
    "cash_amount",
    "check_amount",
    "zelle_amount",
    "gift_card_amount",
    "zelle_verified",
    "gift_card_verified",
    "received_on",
    "zelle_sender",
    "override_capacity",
    "special_admissions",
    "apply_available_benefits",
    "membership_resolution",
    "membership_resolution_reason",
    "waiver_confirmed",
    "waiver_mismatch_accepted",
    "split_rows",
    "member_add",
    "member_kind",
    "member_places",
    "member_months",
    "member_billing",
    "member_first_method",
    "member_received_on",
    "member_zelle_sender",
    "member_zelle_verified",
    "member_starts_on",
    "member_card",
    "member_card_authorization",
    "member_retain",
    "member_credit",
    "member_accepted",
    "member_received",
    "member_minimum_override",
    "member_comped",
    "member_send_confirmation",
)
PAPER_FIELDS = ("paper_signed", "signed_on", "signer_name", "relationship", "minors", "request_key")


def drafts(request):
    now = timezone.now().timestamp()
    return {k: v for k, v in request.session.get(KEY, {}).items() if v.get("expires", 0) > now}


def get(request, booking, token):
    try:
        token = str(uuid.UUID(str(token)))
        value = drafts(request)[token]
    except (ValueError, TypeError, KeyError) as error:
        raise ValidationError(
            "This arrival draft expired. Open the booking and review arrival again."
        ) from error
    if value["booking"] != booking.pk or value["actor"] != request.user.pk:
        raise ValidationError("Return to this booking’s arrival page.")
    if value["version"] != booking.edit_version:
        raise ValidationError(
            "The booking changed while arrival was open. Review its current details before continuing."
        )
    return value


def create(request, booking, initial):
    token = str(uuid.uuid4())
    values = drafts(request)
    values[token] = {
        "booking": booking.pk,
        "actor": request.user.pk,
        "version": booking.edit_version,
        "expires": (timezone.now() + timedelta(hours=2)).timestamp(),
        "fields": {k: str(v) for k, v in initial.items() if k in FIELDS},
        "paper": {},
    }
    request.session[KEY] = dict(list(values.items())[-12:])
    return token


def save(request, booking, token, posted):
    value = get(request, booking, token)
    value["fields"] = {k: str(posted.get(k, ""))[:1000] for k in FIELDS}
    value["paper"] = {k: str(posted.get("paper-" + k, ""))[:18000] for k in PAPER_FIELDS}
    values = drafts(request)
    values[str(token)] = value
    request.session[KEY] = values
    return value


def set_waiver(request, booking, token, share_token):
    value = get(request, booking, token)
    value["waiver_token"] = share_token
    values = drafts(request)
    values[str(token)] = value
    request.session[KEY] = values


def url(booking, token):
    return reverse("booking_arrival", args=[booking.pk]) + "?draft=" + str(token)


def discard(request, token):
    values = drafts(request)
    values.pop(str(token), None)
    request.session[KEY] = values
