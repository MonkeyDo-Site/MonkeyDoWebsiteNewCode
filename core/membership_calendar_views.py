"""Correct an unused membership's dates on its existing overview page."""

import uuid
from datetime import date

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string

from .membership_calendar_changes import (
    ACKNOWLEDGMENT,
    authorize,
    available,
    confirm,
    eligibility,
    review,
    root_for,
)

ACTIONS = {"calendar_review", "calendar_confirm"}


class CalendarForm(forms.Form):
    starts_on = forms.DateField(
        label="Corrected start date", widget=forms.DateInput(attrs={"type": "date"})
    )
    reason = forms.CharField(
        max_length=2000, label="Reason for correction", widget=forms.Textarea(attrs={"rows": 2})
    )
    send_confirmation = forms.ChoiceField(
        label="Email the customer the corrected dates?",
        choices=[("no", "No"), ("yes", "Yes")],
        initial="no",
    )
    customer_confirmed = forms.BooleanField(required=False, label=ACKNOWLEDGMENT)
    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    reviewed = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, prefix="calendar", **kwargs)
        for name in ("starts_on", "reason", "send_confirmation"):
            self.fields[name].widget.attrs["data-calendar-input"] = ""


def shown(data):
    if not data:
        return None
    return data | {
        "starts_on": date.fromisoformat(data["starts_on"]),
        "ends_on": date.fromisoformat(data["ends_on"]),
        "before_starts": date.fromisoformat(data["before"]["starts_on"]),
        "before_ends": date.fromisoformat(data["before"]["ends_on"]),
    }


def controls(request, member):
    action = request.POST.get("action") if request.method == "POST" else ""
    active_action = action in ACTIONS
    if not available():
        if active_action:
            error = "Membership date correction is not available in this release. No dates were changed."
            if request.POST.get("format") == "json":
                return JsonResponse({"error": error}, status=400), {}
            messages.error(request, error)
            return redirect("membership_overview", pk=member.pk), {}
        return None, {}
    history = list(
        member.calendar_corrections.select_related("actor")
        .prefetch_related("messages__message")
        .order_by("-version")[:20]
    )
    can_edit = (
        request.user.has_perm("core.change_membershipdraft") and settings.MEMBERSHIP_SALES_ENABLED
    )
    form, quote, problem = None, None, ""
    if active_action:
        try:
            authorize(request.user)
        except ValidationError as error:
            if request.POST.get("format") == "json":
                return JsonResponse({"error": " ".join(error.messages)}, status=400), {}
            messages.error(request, " ".join(error.messages))
            return redirect("membership_overview", pk=member.pk), {}
    if can_edit:
        try:
            root = eligibility(member)
        except ValidationError as error:
            problem = " ".join(error.messages)
        else:
            form = CalendarForm(
                request.POST if active_action else None, initial=dict(starts_on=root.starts_on)
            )
    if active_action and form is not None and form.is_valid():
        values = form.cleaned_data
        params = dict(
            actor=request.user,
            member_id=member.pk,
            starts_on=values["starts_on"],
            reason=values["reason"],
            send_confirmation=values["send_confirmation"] == "yes",
        )
        try:
            if action == "calendar_confirm":
                saved = confirm(
                    **params,
                    request_key=values["request_key"],
                    reviewed=values["reviewed"],
                    customer_confirmed=values["customer_confirmed"],
                )
                message = "Membership dates corrected. The original purchase and payment history are retained."
                if saved.messages.exists():
                    message += " An updated confirmation email was prepared."
                messages.success(request, message)
                return redirect("membership_overview", pk=member.pk), {}
            quote = review(**params)
            mutable = form.data.copy()
            mutable[form.add_prefix("reviewed")] = quote["fingerprint"]
            mutable[form.add_prefix("customer_confirmed")] = ""
            form.data = mutable
        except ValidationError as error:
            form.add_error(None, error)
    if active_action and request.POST.get("format") == "json":
        if quote:
            return JsonResponse(
                dict(
                    html=render_to_string(
                        "core/partials/membership_calendar_review.html",
                        {"calendar_quote": shown(quote)},
                        request=request,
                    ),
                    fingerprint=quote["fingerprint"],
                )
            ), {}
        errors = [problem]
        if form is not None:
            errors += [str(message) for field in form.errors.values() for message in field]
        return JsonResponse(
            {
                "error": " ".join(error for error in errors if error)
                or "Review the corrected dates and reason."
            },
            status=400,
        ), {}
    return None, dict(
        calendar_form=form,
        calendar_quote=shown(quote),
        calendar_history=history,
        calendar_problem=problem,
        calendar_original=member.membership,
        calendar_current=root_for(member),
    )
