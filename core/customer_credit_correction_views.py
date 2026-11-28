"""Review and confirm rare owner corrections on the existing customer page."""

import uuid
from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string

from .customer_credit_corrections import correct, restorables, review
from .customer_credit_records import CustomerCreditCorrection

ACTIONS = {"credit_correction_preview", "credit_correction_confirm"}


class CorrectionForm(forms.Form):
    kind = forms.ChoiceField(
        choices=CustomerCreditCorrection._meta.get_field("kind").choices, label="Correction"
    )
    value = forms.DecimalField(
        min_value=Decimal("0.01"), max_digits=14, decimal_places=2, label="Amount"
    )
    original = forms.ModelChoiceField(queryset=None, required=False, label="Previous removal")
    reason = forms.CharField(
        max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 2, "required": True})
    )
    request_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    reviewed = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, customer, **kwargs):
        kwargs.setdefault("auto_id", "id_credit_correction_%s")
        super().__init__(*args, **kwargs)
        self.prior = None
        removals = restorables(customer.pk)
        self.fields["original"].queryset = removals
        self.fields["original"].label_from_instance = lambda row: (
            f"{row.created_at:%b %d, %Y} · ${row.unrestored:.2f} left to restore"
            if hasattr(row, "unrestored")
            else f"{row.created_at:%b %d, %Y} · earlier removal ${row.amount:.2f}"
        )
        if self.is_bound:
            try:
                key = forms.UUIDField().clean(self.data.get("request_key"))
                self.prior = CustomerCreditCorrection.objects.filter(
                    pk=key, customer=customer
                ).first()
            except ValidationError:
                pass
            if self.prior and self.prior.original_id:
                self.fields["original"].queryset = CustomerCreditCorrection.objects.filter(
                    pk__in=[*removals.values_list("pk", flat=True), self.prior.original_id]
                )

    def clean(self):
        data = super().clean()
        if data.get("kind") == "restore" and not data.get("original"):
            self.add_error("original", "Choose the earlier removal to restore.")
        if data.get("kind") == "remove" and data.get("original"):
            self.add_error("original", "Clear the earlier removal for a new credit removal.")
        return data


def controls(request, customer):
    action = request.POST.get("action") if request.method == "POST" else None
    allowed = (
        settings.MEMBERSHIP_SALES_ENABLED
        and request.user.is_superuser
        and all(
            request.user.has_perm(name)
            for name in (
                "core.view_paymentoperation",
                "core.view_membershippurchase",
                "core.add_membershippurchase",
                "core.collect_payment",
                "core.review_payment",
            )
        )
    )
    if action in ACTIONS and not allowed:
        raise PermissionDenied
    context = dict(correction_form=None, correction_quote=None)
    if not allowed:
        return None, context
    bound = action in ACTIONS
    form = CorrectionForm(request.POST if bound else None, customer=customer)
    context["correction_form"] = form
    if bound and form.is_valid():
        values = form.cleaned_data
        inputs = dict(
            actor=request.user,
            customer_id=customer.pk,
            kind=values["kind"],
            value=values["value"],
            original_id=values["original"].pk if values["original"] else None,
        )
        try:
            data = form.prior.details if form.prior else review(**inputs)
            context["correction_quote"] = data
            if action == "credit_correction_confirm":
                record = correct(
                    **inputs,
                    reviewed=values["reviewed"],
                    request_key=values["request_key"],
                    reason=values["reason"],
                    confirmed=True,
                )
                messages.success(
                    request,
                    f"Customer credit {'removed' if record.kind == 'remove' else 'restored'}: ${record.amount:.2f}.",
                )
                return redirect("customer_detail", pk=customer.pk), context
            return JsonResponse(
                dict(
                    fingerprint=data["fingerprint"],
                    amount=data["amount"],
                    kind=data["kind"],
                    html=render_to_string(
                        "core/partials/customer_credit_correction_review.html",
                        dict(correction_quote=data),
                        request=request,
                    ),
                )
            ), context
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
    if action == "credit_correction_preview":
        return JsonResponse(
            dict(error=" ".join(str(error) for errors in form.errors.values() for error in errors)),
            status=400,
        ), context
    if action == "credit_correction_confirm" and form.errors and context["correction_quote"]:
        form.data = form.data.copy()
        form.data["reviewed"] = context["correction_quote"]["fingerprint"]
    return None, context
