"""Partial receipt and remaining-card controls share the existing membership overview."""

import uuid
from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string

from .membership_paid_visit_manual import TENDERS
from .membership_paid_visit_split import (
    available,
    card_review,
    confirm_split,
    latest,
    plan,
    request_card,
    review,
)

ACTIONS = {"paid_visit_split_review", "paid_visit_split_confirm", "paid_visit_split_retry"}


class SplitForm(forms.Form):
    manual_amount = forms.DecimalField(
        label="Received amount to apply", min_value=Decimal("0.01"), max_digits=14, decimal_places=2
    )
    tender = forms.ChoiceField(label="Received payment", choices=TENDERS.items())
    method = forms.ModelChoiceField(label="Card for the remaining amount", queryset=None)
    received_on = forms.DateField(
        label="Zelle bank receipt date",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    sender_name = forms.CharField(
        label="Zelle sender shown by the bank", max_length=160, required=False
    )
    verified_received = forms.BooleanField(
        required=False,
        label="I verified the payment shown was received and has not already been recorded elsewhere.",
    )
    card_authorized = forms.BooleanField(
        required=False, label="The customer authorizes the remaining card payment shown."
    )
    request_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    reviewed = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, intent, **kwargs):
        from .membership_paid_visit_recovery import cards
        from .membership_sales import today

        super().__init__(*args, prefix="paid-visit-split", **kwargs)
        self.fields["method"].queryset = cards(intent)
        self.fields["method"].label_from_instance = lambda card: (
            f"{card.brand or 'Card'} ending in {card.last_four}"
        )
        self.initial.setdefault("method", self.fields["method"].queryset.first())
        self.initial.setdefault("received_on", today())
        for name in ("manual_amount", "tender", "method", "received_on", "sender_name"):
            self.fields[name].widget.attrs["data-paid-visit-split-input"] = ""

    def values(self):
        data = self.cleaned_data
        return dict(
            manual_amount=data["manual_amount"],
            tender=data["tender"],
            method_id=data["method"].pk,
            received_on=data.get("received_on") if data["tender"] == "zelle" else None,
            sender_name=data.get("sender_name", "") if data["tender"] == "zelle" else "",
        )


def controls(request, member, pending):
    action = request.POST.get("action") if request.method == "POST" else ""
    active_action = action in ACTIONS
    context = {"paid_visit_split": None}
    can_act = settings.MEMBERSHIP_SALES_ENABLED and all(
        request.user.has_perm(name)
        for name in ("core.add_membershippurchase", "core.collect_payment", "core.change_booking")
    )
    if active_action and not can_act:
        raise PermissionDenied
    if not available() or not pending or pending["stopped"]:
        if active_action:
            problem = "This split-payment option is not available for this visit application. No new payment was recorded."
            if request.POST.get("format") == "json":
                return JsonResponse({"error": problem}, status=400), context
            messages.error(request, problem)
            return redirect("membership_overview", pk=member.pk), context
        return None, context
    intent = pending["intent"]
    saved = plan(intent)
    if saved:
        if action == "paid_visit_split_review":
            problem = "A partial payment is already recorded. Use its remaining-card controls; do not record that receipt again."
            if request.POST.get("format") == "json":
                return JsonResponse({"error": problem}, status=400), context
            messages.error(request, problem)
            return redirect("membership_overview", pk=member.pk), context
        current = latest(saved)
        data = dict(
            saved=saved,
            facts=saved.facts,
            operation=saved.operation,
            card=current,
            choices=[],
            key=uuid.uuid4(),
        )
        if can_act and not member.cancellations.exists():
            from .membership_paid_visit_recovery import cards

            for method in cards(intent):
                try:
                    quote = card_review(actor=request.user, split_id=saved.pk, method_id=method.pk)
                except (ValidationError, PermissionDenied):
                    continue
                data["choices"].append(
                    dict(
                        value=f"{method.pk}:{quote['fingerprint']}",
                        label=f"{method.brand or 'Card'} ending in {method.last_four}",
                    )
                )
        if active_action:
            try:
                if action != "paid_visit_split_retry":
                    # A repeated original submit uses its exact identity and
                    # receipt proof; it cannot invent a second partial payment.
                    form = SplitForm(request.POST, intent=intent)
                    if not form.is_valid():
                        raise ValidationError("Open the recorded split payment before continuing.")
                    confirm_split(
                        actor=request.user,
                        intent_id=intent.pk,
                        **form.values(),
                        request_key=form.cleaned_data["request_key"],
                        reviewed=form.cleaned_data["reviewed"],
                        verified_received=form.cleaned_data["verified_received"],
                        card_authorized=form.cleaned_data["card_authorized"],
                    )
                else:
                    choice = request.POST.get("split_card_choice", "").split(":", 1)
                    if len(choice) != 2:
                        raise ValidationError(
                            "Choose an available card and review the remaining amount."
                        )
                    request_card(
                        actor=request.user,
                        split_id=saved.pk,
                        method_id=forms.UUIDField().clean(choice[0]),
                        request_key=forms.UUIDField().clean(request.POST.get("split_card_key")),
                        reviewed=choice[1],
                        confirmed=request.POST.get("split_card_authorized") == "on",
                    )
                messages.success(
                    request,
                    "This split receipt is already recorded. Review its existing card status below.",
                )
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
            return redirect("membership_overview", pk=member.pk), context
        context["paid_visit_split"] = data
        return None, context
    if not can_act:
        return None, context
    # Only known failed requests offer a new received/card allocation.
    from .membership_paid_visit_recovery import source_review

    try:
        source_review(actor=request.user, intent_id=intent.pk)
    except (ValidationError, PermissionDenied) as error:
        if active_action:
            problem = (
                " ".join(getattr(error, "messages", []))
                or "Review the existing payment outcome before changing this payment."
            )
            if request.POST.get("format") == "json":
                return JsonResponse({"error": problem}, status=400), context
            messages.error(request, problem)
            return redirect("membership_overview", pk=member.pk), context
        return None, context
    form = SplitForm(request.POST if active_action else None, intent=intent)
    quote = None
    if active_action and form.is_valid():
        try:
            if action == "paid_visit_split_confirm":
                saved, card, problem = confirm_split(
                    actor=request.user,
                    intent_id=intent.pk,
                    **form.values(),
                    request_key=form.cleaned_data["request_key"],
                    reviewed=form.cleaned_data["reviewed"],
                    verified_received=form.cleaned_data["verified_received"],
                    card_authorized=form.cleaned_data["card_authorized"],
                )
                if problem:
                    messages.warning(request, problem)
                else:
                    messages.success(
                        request,
                        f"{TENDERS[saved.facts['tender']]} ${saved.facts['manual_net']} recorded. Card payment ${card.operation.amount} requested; its result is not yet confirmed.",
                    )
                return redirect("membership_overview", pk=member.pk), context
            if action != "paid_visit_split_review":
                raise ValidationError("Review the split payment before confirming.")
            quote = review(actor=request.user, intent_id=intent.pk, **form.values())
            quote["tender_label"] = TENDERS[quote["tender"]].lower()
            form.data = form.data.copy()
            form.data[form.add_prefix("reviewed")] = quote["fingerprint"]
            for field in ("verified_received", "card_authorized"):
                form.data.pop(form.add_prefix(field), None)
        except ValidationError as error:
            form.add_error(None, error)
            form.data = form.data.copy()
            for field in ("reviewed", "verified_received", "card_authorized"):
                form.data.pop(form.add_prefix(field), None)
    if active_action and request.POST.get("format") == "json":
        if quote:
            return JsonResponse(
                dict(
                    html=render_to_string(
                        "core/partials/membership_paid_visit_split_review.html",
                        {"split_quote": quote},
                        request=request,
                    ),
                    fingerprint=quote["fingerprint"],
                    card_total=quote["card_total"],
                    tender=quote["tender"],
                    tender_label=quote["tender_label"],
                )
            ), context
        return JsonResponse(
            {
                "error": " ".join(str(error) for errors in form.errors.values() for error in errors)
                or "Review the split-payment details."
            },
            status=400,
        ), context
    context["paid_visit_split"] = dict(form=form, quote=quote)
    return None, context
