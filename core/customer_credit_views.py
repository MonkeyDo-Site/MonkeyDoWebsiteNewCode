"""Credit review and confirmation remain on the membership overview."""

import uuid

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string

from .customer_credit import apply, balance, review
from .customer_credit_records import CustomerCreditApplication
from .membership_sales import installment_paid, today

ACTIONS = {"credit_preview", "credit_confirm"}


class CreditForm(forms.Form):
    installment = forms.ModelChoiceField(queryset=None, label="Due installment")
    value = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=14,
        decimal_places=2,
        label="Customer credit to apply",
        help_text="Leave blank to use available credit up to the unpaid membership amount.",
    )
    request_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    reviewed = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, member, **kwargs):
        kwargs.setdefault("auto_id", "id_customer_credit_%s")
        super().__init__(*args, **kwargs)
        dues = member.installments.select_related("cycle", "invoice__sale").filter(
            due_on__lte=today()
        )
        if member.billing_state.stopped_on:
            dues = dues.filter(cycle__starts_on__lt=member.billing_state.stopped_on)
        self.fields["installment"].queryset = dues.filter(
            pk__in=[item.pk for item in dues if not installment_paid(item)]
        )
        self.prior = None
        if self.is_bound:
            try:
                key = forms.UUIDField().clean(self.data.get("request_key"))
                self.prior = CustomerCreditApplication.objects.filter(
                    pk=key, sale__membership_invoice__installment__purchase=member
                ).first()
            except ValidationError:
                pass
            if self.prior:
                chosen = list(self.fields["installment"].queryset.values_list("pk", flat=True))
                chosen.append(self.prior.sale.membership_invoice.installment_id)
                self.fields["installment"].queryset = member.installments.filter(pk__in=chosen)
        self.fields["installment"].label_from_instance = lambda item: (
            f"Month {item.number} · due {item.due_on:%b %d, %Y}"
        )
        self.initial["installment"] = self.fields["installment"].queryset.first()


def controls(request, member):
    action = request.POST.get("action") if request.method == "POST" else None
    allowed = all(
        request.user.has_perm(name)
        for name in ("core.add_membershippurchase", "core.collect_payment")
    )
    if action in ACTIONS and not allowed:
        raise PermissionDenied
    context = dict(credit_form=None, credit_quote=None, credit_problem="")
    if not allowed or (not balance(member.customer_id) and action not in ACTIONS):
        return None, context
    bound = action in ACTIONS
    form = CreditForm(request.POST if bound else None, member=member)
    context["credit_form"] = form
    values = form.cleaned_data if bound and form.is_valid() else None
    item = (
        values.get("installment") if values else form.initial["installment"] if not bound else None
    )
    if item:
        try:
            data = (
                form.prior.details
                if form.prior
                else review(
                    actor=request.user,
                    member_id=member.pk,
                    installment_id=item.pk,
                    value=values.get("value") if values else None,
                )
            )
            context["credit_quote"] = data
            if not bound:
                form.initial["reviewed"] = data["fingerprint"]
            elif action == "credit_confirm":
                apply(
                    actor=request.user,
                    member_id=member.pk,
                    installment_id=item.pk,
                    value=values["value"],
                    reviewed=values["reviewed"],
                    request_key=values["request_key"],
                    confirmed=True,
                )
                messages.success(
                    request,
                    "Customer credit applied. No new payment was received and no card was charged.",
                )
                return redirect("membership_overview", pk=member.pk), context
            if action == "credit_preview":
                return JsonResponse(
                    dict(
                        fingerprint=data["fingerprint"],
                        amount=data["amount"],
                        html=render_to_string(
                            "core/partials/customer_credit_review.html",
                            dict(credit_quote=data),
                            request=request,
                        ),
                    )
                ), context
        except ValidationError as exc:
            if bound:
                form.add_error(None, " ".join(exc.messages))
            else:
                context["credit_problem"] = " ".join(exc.messages)
    elif not bound:
        context["credit_form"] = None
    if action == "credit_preview":
        return JsonResponse(
            dict(error=" ".join(str(error) for errors in form.errors.values() for error in errors)),
            status=400,
        ), context
    if action == "credit_confirm" and form.errors and context["credit_quote"]:
        form.data = form.data.copy()
        form.data["reviewed"] = context["credit_quote"]["fingerprint"]
    return None, context
