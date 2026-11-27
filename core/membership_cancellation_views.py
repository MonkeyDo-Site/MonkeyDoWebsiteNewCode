"""Cancellation and original-source refund controls on the existing overview."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string

from .membership_cancellations import (
    cancel,
    plan_paid,
    plan_pending,
    request_refund,
    review,
    unrecorded_provider_return,
)
from .membership_records import MembershipCancellation, MembershipRefundPlan
from .pagination import paginate
from .payments.amounts import ZERO
from .payments.gateway import ProviderFailure

ACTIONS = {"cancel_preview", "cancel_confirm", "refund_confirm"}


class CancellationForm(forms.Form):
    timing = forms.ChoiceField(
        label="Effective end",
        choices=[
            ("end_cycle", "End of the current membership month"),
            ("immediate", "Immediately"),
        ],
        initial="end_cycle",
    )
    refund_amount = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=14,
        decimal_places=2,
        label="Owner refund amount",
        help_text="Leave blank to use the suggested amount shown. Only actual paid membership funds can be returned; original card fees remain separate.",
    )
    early_override = forms.BooleanField(
        required=False, label="Owner: approve cancellation during the initial commitment"
    )
    reason = forms.CharField(
        max_length=500, label="Cancellation reason", widget=forms.Textarea(attrs={"rows": 2})
    )
    refund_action = forms.ChoiceField(
        label="Refund handling",
        choices=[
            ("due", "Record refund due; handle it afterward"),
            ("process", "Request card refunds / record completed non-card returns now"),
        ],
        initial="due",
    )
    manual_refunds_confirmed = forms.BooleanField(
        required=False,
        label="I confirm the non-card refunds listed above were actually returned today",
    )
    send_confirmation = forms.ChoiceField(
        label="Send cancellation email?",
        choices=[("", "Choose Yes or No"), ("yes", "Yes"), ("no", "No")],
    )
    request_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    reviewed = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, previewing=False, **kwargs):
        kwargs.setdefault("auto_id", "id_membership_cancel_%s")
        super().__init__(*args, **kwargs)
        self.fields["reason"].required = not previewing
        self.fields["send_confirmation"].required = not previewing


class RefundForm(forms.Form):
    plan_id = forms.UUIDField(widget=forms.HiddenInput)
    request_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    refund_amount = forms.DecimalField(
        required=False,
        min_value=Decimal("0.01"),
        max_digits=14,
        decimal_places=2,
        label="Refund amount",
        help_text="Leave blank for the full remaining amount. Record only what was actually returned for non-card refunds.",
    )
    reviewed_balance = forms.DecimalField(
        min_value=Decimal("0.01"), max_digits=14, decimal_places=2, widget=forms.HiddenInput
    )
    manual_returned = forms.BooleanField(
        required=False, label="I confirm this refund has actually been returned to the customer"
    )
    received_on = forms.DateField(
        required=False,
        label="Actual refund date",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Leave blank for today.",
    )
    card_refund_action = forms.ChoiceField(
        required=False,
        label="Card refund action",
        choices=[
            ("request", "Request a new refund"),
            ("record", "Record a refund already completed in Banquest"),
        ],
        initial="request",
    )
    completed_provider_reference = forms.CharField(
        required=False, max_length=40, label="Completed Banquest refund transaction reference"
    )
    completed_confirmed = forms.BooleanField(
        required=False, label="This refund was already completed in Banquest"
    )

    def __init__(self, *args, plan, **kwargs):
        kwargs.setdefault("auto_id", f"id_member_refund_{plan.pk}_%s")
        super().__init__(*args, **kwargs)
        self.initial["plan_id"] = plan.pk
        self.initial["refund_amount"] = self.initial["reviewed_balance"] = max(
            ZERO, plan.amount - plan_paid(plan)
        )
        if plan.original.tender == "card":
            self.fields.pop("manual_returned")
            self.fields.pop("received_on")
            if unrecorded_provider_return(plan.original):
                self.initial["card_refund_action"] = "record"
        else:
            self.fields["manual_returned"].required = True
            for name in (
                "card_refund_action",
                "completed_provider_reference",
                "completed_confirmed",
            ):
                self.fields.pop(name)

    def clean(self):
        values = super().clean()
        if values.get("card_refund_action") == "record":
            if not values.get("completed_provider_reference"):
                self.add_error(
                    "completed_provider_reference", "Enter the completed refund reference."
                )
            if not values.get("completed_confirmed"):
                self.add_error("completed_confirmed", "Confirm the refund already completed.")
        elif values.get("completed_provider_reference") or values.get("completed_confirmed"):
            self.add_error("card_refund_action", "Choose to record the completed Banquest refund.")
        return values


def displayed(data, member):
    stop = date.fromisoformat(data["stopped_on"])
    return data | dict(
        stopped_date=stop,
        effective_end=stop if data["timing"] == "immediate" else stop - timedelta(days=1),
        before_start=date.fromisoformat(data["on"]) < member.membership.starts_on,
        has_manual=any(plan["tender"] != "card" for plan in data["plans"]),
    )


def overview_controls(request, member):
    action = request.POST.get("action") if request.method == "POST" else None
    if action in ACTIONS and not request.user.is_superuser:
        raise PermissionDenied
    cancellation = member.cancellations.order_by("-created_at").first()
    context = dict(
        cancellation=cancellation,
        cancel_form=None,
        cancel_quote=None,
        cancel_problem="",
        refund_rows=[],
    )
    response = None
    if request.user.is_superuser and (
        cancellation is None or action in {"cancel_preview", "cancel_confirm"}
    ):
        bound = action in {"cancel_preview", "cancel_confirm"}
        form = CancellationForm(
            request.POST if bound else None, previewing=action == "cancel_preview"
        )
        context["cancel_form"] = form
        if not bound or form.is_valid():
            values = form.cleaned_data if bound else dict(timing="end_cycle", refund_amount=None)
            try:
                prior = (
                    MembershipCancellation.objects.filter(
                        pk=values["request_key"], purchase=member
                    ).first()
                    if bound
                    else None
                )
                data = (
                    prior.snapshot
                    if prior
                    else review(
                        actor=request.user,
                        member_id=member.pk,
                        timing=values["timing"],
                        refund_amount=values.get("refund_amount"),
                    )
                )
                context["cancel_quote"] = displayed(data, member)
                if not bound:
                    form.initial["reviewed"] = data["fingerprint"]
                elif action == "cancel_confirm":
                    cancel(
                        actor=request.user,
                        member_id=member.pk,
                        timing=values["timing"],
                        refund_amount=data["refund_amount"],
                        reviewed=values["reviewed"],
                        request_key=values["request_key"],
                        reason=values["reason"],
                        early_override=values["early_override"],
                        send_confirmation=values["send_confirmation"] == "yes",
                        refund_now=values["refund_action"] == "process",
                        manual_refunds_confirmed=values["manual_refunds_confirmed"],
                    )
                    messages.success(
                        request,
                        "Membership cancellation recorded. Review any refund still due below; pending refunds are not completed returns.",
                    )
                    return redirect("membership_overview", pk=member.pk), context
                if action == "cancel_preview":
                    return JsonResponse(
                        dict(
                            html=render_to_string(
                                "core/partials/membership_cancellation_review.html",
                                {"cancel_quote": displayed(data, member)},
                                request=request,
                            ),
                            fingerprint=data["fingerprint"],
                            refund_amount=data["refund_amount"],
                            requires_early_override=data["requires_early_override"],
                            has_manual=any(plan["tender"] != "card" for plan in data["plans"]),
                        )
                    ), context
            except ValidationError as exc:
                if bound:
                    form.add_error(None, " ".join(exc.messages))
                else:
                    context["cancel_problem"] = " ".join(exc.messages)
                    context["cancel_form"] = None
        if action == "cancel_preview":
            return JsonResponse(
                {
                    "error": " ".join(
                        str(error) for errors in form.errors.values() for error in errors
                    )
                },
                status=400,
            ), context
    if action == "cancel_confirm" and context["cancel_quote"] and context["cancel_form"].errors:
        context["cancel_form"].data = context["cancel_form"].data.copy()
        context["cancel_form"].data["reviewed"] = context["cancel_quote"]["fingerprint"]
    selected = None
    if action == "refund_confirm":
        try:
            selected_id = forms.UUIDField().clean(request.POST.get("plan_id"))
            selected = MembershipRefundPlan.objects.select_related("original", "cancellation").get(
                pk=selected_id, cancellation__purchase=member
            )
        except (ValidationError, MembershipRefundPlan.DoesNotExist):
            raise PermissionDenied from None
        form = RefundForm(request.POST, plan=selected)
        if form.is_valid():
            try:
                values = form.cleaned_data
                request_refund(
                    actor=request.user,
                    plan_id=selected.pk,
                    request_key=values["request_key"],
                    confirmed=True,
                    manual_returned=values.get("manual_returned", False),
                    received_on=values.get("received_on"),
                    refund_amount=values["refund_amount"]
                    if values["refund_amount"] is not None
                    else values["reviewed_balance"],
                    completed_provider_reference=values.get("completed_provider_reference", ""),
                )
                messages.success(
                    request,
                    "Completed Banquest refund verified and recorded."
                    if values.get("card_refund_action") == "record"
                    else "Refund requested. Check its outcome before another attempt."
                    if selected.original.tender == "card"
                    else "Completed non-card refund recorded.",
                )
                return redirect("membership_overview", pk=member.pk), context
            except (ValidationError, ProviderFailure) as exc:
                form.add_error(
                    None,
                    " ".join(exc.messages)
                    if isinstance(exc, ValidationError)
                    else "Banquest could not verify the completed refund. Nothing was recorded and no new refund was sent. Check the reference and try verification again.",
                )
    plans = (
        MembershipRefundPlan.objects.filter(cancellation__purchase=member)
        .select_related("original__method", "cancellation")
        .order_by("created_at", "pk")
    )
    refund_page = paginate(request, plans)
    context["refund_page"] = refund_page
    for plan in refund_page:
        paid = plan_paid(plan)
        context["refund_rows"].append(
            dict(
                plan=plan,
                returned=paid,
                remaining=max(ZERO, plan.amount - paid),
                pending=plan_pending(plan),
                external_return=unrecorded_provider_return(plan.original),
                attempt=plan.attempts.select_related("operation").order_by("-created_at").first(),
                form=form if selected and selected.pk == plan.pk else RefundForm(plan=plan),
            )
        )
    return response, context
