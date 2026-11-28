"""Choose and confirm several renewal cohorts on one compact staff page."""

import uuid
from datetime import date

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms import formset_factory
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .membership_batch_records import MembershipRenewalBatch
from .membership_batch_renewals import available, confirm, review
from .membership_records import MembershipPurchase
from .membership_renewals import renewal_details
from .membership_sales import authorize
from .models import Customer, PaymentMethod
from .permissions import require_actor, staff_permission


class RenewalRow(forms.Form):
    renew = forms.BooleanField(required=False, label="Renew these places")
    prior_id = forms.IntegerField(widget=forms.HiddenInput)
    kind = forms.ChoiceField(choices=[("subscription", "Subscription"), ("unlimited", "Unlimited")])
    places = forms.IntegerField(min_value=1, label="Places")
    months = forms.IntegerField(min_value=1, label="Months")
    billing = forms.ChoiceField(choices=[("prepaid", "Pay in full"), ("monthly", "Monthly")])
    method_id = forms.ChoiceField(required=False, label="Card for future installments")
    minimum_override = forms.BooleanField(required=False, label="Owner: allow a shorter renewal")

    def __init__(self, *args, cards=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["method_id"].choices = [("", "Choose a saved card")] + list(cards)
        for name, field in self.fields.items():
            if name != "prior_id":
                field.widget.attrs["data-batch-input"] = ""

    def clean(self):
        data = super().clean()
        if not data.get("renew"):
            self._errors.clear()
            return {"renew": False}
        return data


class CheckoutForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    reviewed = forms.CharField(required=False, widget=forms.HiddenInput)
    tender = forms.ChoiceField(
        choices=[("cash", "Cash received"), ("check", "Check received")], label="Payment method"
    )
    accepted = forms.BooleanField(
        required=False, label="The customer accepted the reviewed membership terms."
    )
    verified_received = forms.BooleanField(
        required=False, label="I verified that the full payment shown was actually received."
    )


def displayed_quote(data):
    if not data:
        return None
    return data | {
        "lines": [
            line
            | {
                "starts_date": date.fromisoformat(line["offer"]["starts_on"]),
                "ends_date": date.fromisoformat(line["offer"]["ends_on"]),
                "schedule": [
                    {"day": date.fromisoformat(item["due_on"]), "amount": item["quote"]["total"]}
                    for item in line["offer"]["installments"]
                ],
            }
            for line in data["lines"]
        ]
    }


@staff_permission("core.view_membershippurchase")
@require_http_methods(["GET", "POST"])
def renew_memberships(request, customer_pk):
    require_actor(request.user, "core.view_customer")
    customer = get_object_or_404(Customer, pk=customer_pk)
    batch = None
    if request.method == "GET" and request.GET.get("checkout"):
        if not available():
            raise Http404
        try:
            key = uuid.UUID(request.GET["checkout"])
        except (ValueError, TypeError):
            raise Http404 from None
        batch = get_object_or_404(MembershipRenewalBatch, pk=key, customer=customer)
        return render(
            request,
            "core/membership_batch_renewals.html",
            {
                "customer": customer,
                "batch": batch,
                "parts": batch.parts.select_related("purchase__membership").order_by("position"),
            },
        )
    if not settings.MEMBERSHIP_SALES_ENABLED:
        raise Http404
    authorize(request.user, collect=True)
    candidates, initial, unavailable = [], [], []
    for member in (
        MembershipPurchase.objects.filter(customer=customer)
        .select_related("membership", "billing_state__mandate")
        .order_by("membership__ends_on", "pk")[:100]
    ):
        try:
            details = renewal_details(member)
            if not details["available_places"]:
                continue
        except ValidationError as error:
            unavailable.append((member, " ".join(error.messages)))
            continue
        candidates.append((member, details))
        initial.append(
            dict(
                prior_id=member.pk,
                kind=member.membership.kind,
                places=details["available_places"],
                months=details["minimum_months"],
                billing=member.membership.billing,
                method_id=str(member.billing_state.mandate.method_id)
                if member.billing_state.mandate
                else "",
            )
        )
    cards = [
        (str(card.pk), f"{card.brand} · ending in {card.last_four}")
        for card in PaymentMethod.objects.filter(
            customer=customer, state="active", environment="sandbox"
        )
        .exclude(provider_method__isnull=True)
        .order_by("-created_at")
    ]
    Rows = formset_factory(RenewalRow, extra=0, max_num=100, validate_max=True, absolute_max=100)
    formset = Rows(
        request.POST if request.method == "POST" else None,
        initial=initial,
        prefix="renewals",
        form_kwargs={"cards": cards},
    )
    checkout = CheckoutForm(
        request.POST if request.method == "POST" else None,
        initial={"request_key": uuid.uuid4(), "tender": "cash"},
    )
    checkout.fields["tender"].widget.attrs["data-batch-input"] = ""
    data = None
    action = request.POST.get("action", "review")
    if request.method == "POST" and formset.is_valid() and checkout.is_valid():
        selected = [
            {key: value for key, value in item.cleaned_data.items() if key != "renew"}
            for item in formset
            if item.cleaned_data.get("renew")
        ]
        for row in selected:
            if row["billing"] == "prepaid":
                row["method_id"] = None
        try:
            values = dict(
                actor=request.user,
                customer=customer,
                rows=selected,
                tender=checkout.cleaned_data["tender"],
            )
            if action == "confirm":
                saved = confirm(
                    **values,
                    request_key=checkout.cleaned_data["request_key"],
                    reviewed=checkout.cleaned_data["reviewed"],
                    accepted=checkout.cleaned_data["accepted"],
                    verified_received=checkout.cleaned_data["verified_received"],
                )
                return redirect(
                    reverse("membership_renewals", args=[customer.pk])
                    + "?checkout="
                    + str(saved.pk)
                )
            data = review(**values)
            mutable = checkout.data.copy()
            mutable["reviewed"] = data["fingerprint"]
            mutable["accepted"] = ""
            mutable["verified_received"] = ""
            checkout.data = mutable
        except ValidationError as error:
            checkout.add_error(None, error)
    if request.method == "POST" and request.POST.get("format") == "json":
        if data:
            return JsonResponse(
                dict(
                    html=render_to_string(
                        "core/partials/membership_batch_review.html",
                        {"quote": displayed_quote(data)},
                        request=request,
                    ),
                    fingerprint=data["fingerprint"],
                    button=f"Confirm renewals and record {data['tender']} — ${data['amount']}",
                )
            )
        errors = [*checkout.non_field_errors(), *formset.non_form_errors()]
        for item in formset:
            errors.extend(message for field in item.errors.values() for message in field)
        errors.extend(message for field in checkout.errors.values() for message in field)
        return JsonResponse(
            {
                "error": " ".join(dict.fromkeys(errors))
                or "Select at least one renewal and complete its details."
            },
            status=400,
        )
    metadata = {member.pk: (member, details) for member, details in candidates}
    display = []
    for item in formset:
        try:
            original_id = int(item["prior_id"].value())
        except (TypeError, ValueError):
            original_id = None
        member, details = metadata.get(original_id, (None, None))
        display.append((item, member, details))
    return render(
        request,
        "core/membership_batch_renewals.html",
        dict(
            customer=customer,
            batch=batch,
            parts=batch.parts.select_related("purchase__membership").order_by("position")
            if batch
            else [],
            rows=display,
            formset=formset,
            checkout=checkout,
            quote=displayed_quote(data),
            unavailable=unavailable,
        ),
    )
