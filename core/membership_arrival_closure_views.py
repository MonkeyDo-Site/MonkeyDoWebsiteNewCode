"""The owner stop control stays with the current pending-arrival review."""

import uuid

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import membership_arrival_closure as service
from .membership_records import MembershipArrivalIntent
from .permissions import staff_permission


class StopArrivalForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    reviewed_hash = forms.CharField(min_length=64, max_length=64, widget=forms.HiddenInput)
    reason = forms.CharField(max_length=500, label="Reason for stopping this arrival")
    confirmed = forms.BooleanField(label="Keep the original booking and membership purchase.")

    def __init__(self, *args, actor, intent, **kwargs):
        super().__init__(*args, auto_id="id_stop_%s", **kwargs)
        self.actor, self.intent = actor, intent
        if service.cancellation_for(intent):
            self.fields[
                "confirmed"
            ].label = "Keep the original booking; membership cancellation and refund stay separate."
        if not self.is_bound:
            _, digest = service.review(actor=actor, intent=intent)
            self.initial.update(request_key=uuid.uuid4(), reviewed_hash=digest)

    def save(self):
        return service.stop(actor=self.actor, intent_id=self.intent.pk, **self.cleaned_data)


def controls(request, intent):
    from .membership_schema import available

    if (
        not request.user.is_superuser
        or intent.progress.code != "owner_review_requested"
        or not available("core_membershiparrivalclosure")
    ):
        return {}
    cancellation = service.cancellation_for(intent)
    context = (
        {"stop_cancellation": service.cancellation_snapshot(cancellation)} if cancellation else {}
    )
    try:
        form = StopArrivalForm(actor=request.user, intent=intent)
    except ValidationError as error:
        return context | {"stop_block_reason": " ".join(error.messages), "stop_intent": intent}
    saved = request.session.get("pending_stop_reason", {})
    if saved.get("intent") == str(intent.pk) and saved.get("booking") == intent.booking_id:
        form.initial["reason"] = saved.get("reason", "")
    return context | {"stop_arrival_form": form, "stop_intent": intent}


@staff_permission("core.view_booking")
@require_POST
def stop_arrival(request, pk, intent_id):
    try:
        service.require_owner(request.user)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
        return redirect("booking_detail", pk=pk)
    intent = get_object_or_404(
        MembershipArrivalIntent.objects.select_related("progress", "purchase"),
        pk=intent_id,
        booking_id=pk,
    )
    form = StopArrivalForm(request.POST, actor=request.user, intent=intent)
    if form.is_valid():
        try:
            form.save()
        except ValidationError as error:
            form.add_error(None, error)
        else:
            from .payments import arrival_drafts

            for token, draft in list(arrival_drafts.drafts(request).items()):
                if draft["booking"] == pk and draft["fields"].get("pending_review") == str(
                    intent.pk
                ):
                    arrival_drafts.discard(request, token)
            request.session.pop("pending_stop_reason", None)
            messages.success(
                request, "Arrival stopped. Review the booking’s current details below."
            )
            return redirect("booking_detail", pk=pk)
    request.session["pending_stop_reason"] = dict(
        booking=pk, intent=str(intent.pk), reason=str(request.POST.get("reason", ""))[:500]
    )
    messages.error(request, " ".join(e for errors in form.errors.values() for e in errors))
    return redirect(
        reverse("booking_arrival", args=[pk])
        + ("" if service.cancellation_for(intent) else "?review_pending=1")
    )
