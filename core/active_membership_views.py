"""Compact, explicit staff membership purchase and read-only overview."""

import uuid
from datetime import date

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from .booking_forms import CustomerChoice, customer_picker
from .forms import payment_method_choices
from .membership_records import MembershipInvoice, MembershipPurchase
from .membership_reservations import summary_for
from .membership_sales import installment_paid, membership_status, offer, purchase, today
from .models import Customer, MembershipDraft, PaymentMethod, PricingPolicy
from .pagination import paginate
from .payments.amounts import ZERO
from .payments.invoices import received, total
from .permissions import staff_permission

OFFER_FIELDS = (
    "customer",
    "kind",
    "places",
    "months",
    "billing",
    "starts_on",
    "expected_method",
    "minimum_override",
    "comped",
)


class PurchaseForm(forms.Form):
    customer = CustomerChoice(queryset=Customer.objects.order_by("last_name", "pk"))
    kind = forms.ChoiceField(
        label="Membership", choices=MembershipDraft._meta.get_field("kind").choices
    )
    places = forms.IntegerField(
        min_value=1, max_value=2147483647, initial=1, label="Membership places"
    )
    months = forms.IntegerField(min_value=3, initial=3)
    billing = forms.ChoiceField(choices=MembershipDraft._meta.get_field("billing").choices)
    starts_on = forms.DateField(
        initial=today, label="Starts on", widget=forms.DateInput(attrs={"type": "date"})
    )
    expected_method = forms.ChoiceField(label="First payment")
    minimum_override = forms.BooleanField(
        required=False, label="Owner: allow a one- or two-month term"
    )
    comped = forms.BooleanField(required=False, label="Owner: complimentary membership")
    send_confirmation = forms.ChoiceField(
        required=False,
        label="Send complimentary confirmation email?",
        choices=[("", "Choose Yes or No"), ("yes", "Yes"), ("no", "No")],
    )
    method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.none(),
        required=False,
        label="Saved card",
        empty_label="Choose a saved card",
    )
    verified_received = forms.BooleanField(
        required=False, label="I confirm this membership payment was received"
    )
    accepted = forms.BooleanField(
        required=False,
        label="The customer accepts the membership terms and the scheduled payments shown above",
    )
    request_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    reviewed = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, owner=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expected_method"].choices = payment_method_choices(
            PricingPolicy.objects.first()
        )
        labels = {
            "card": "Credit card",
            "cash": "Cash",
            "check": "Check",
            "zelle": "Zelle",
            "gift_card": "Gift card (verified)",
        }
        self.fields["expected_method"].choices = [
            (key, labels.get(key, label)) for key, label in self.fields["expected_method"].choices
        ]
        if owner:
            self.fields["months"] = forms.IntegerField(min_value=1, initial=3)
        else:
            for name in ("minimum_override", "comped", "send_confirmation"):
                self.fields.pop(name)
        customer_picker(self)
        customer_id = (self.data if self.is_bound else self.initial).get("customer")
        if (
            str(customer_id).isascii()
            and str(customer_id).isdigit()
            and len(str(customer_id)) <= 18
        ):
            self.fields["method"].queryset = PaymentMethod.objects.filter(
                customer_id=customer_id,
                state="active",
                reusable=True,
                environment="sandbox",
                provider_method__isnull=False,
            ).order_by("last_four", "pk")
        self.fields["method"].label_from_instance = lambda card: (
            f"{card.brand} ending in {card.last_four}"
        )

    def offer_values(self):
        return {name: self.cleaned_data.get(name, False) for name in OFFER_FIELDS}


def check_enabled():
    if not settings.MEMBERSHIP_SALES_ENABLED:
        raise Http404


def display_offer(data):
    if data is None:
        return None
    return data | {
        "starts_on": date.fromisoformat(data["starts_on"]),
        "ends_on": date.fromisoformat(data["ends_on"]),
        "installments": [
            item | {"due_on": date.fromisoformat(item["due_on"])} for item in data["installments"]
        ],
    }


@staff_permission("core.view_membershippurchase")
@staff_permission("core.view_customer")
@require_safe
def memberships(request):
    check_enabled()
    records = MembershipPurchase.objects.select_related(
        "membership", "customer", "billing_state"
    ).prefetch_related("installments__invoice__sale")
    customer = request.GET.get("customer", "")
    if customer.isascii() and customer.isdigit() and len(customer) <= 18:
        records = records.filter(customer_id=customer)
    page = paginate(request, records.order_by("-accepted_at", "-pk"))
    rows = [(member, membership_status(member)) for member in page.object_list]
    return render(request, "core/active_memberships.html", {"memberships": page, "rows": rows})


@staff_permission("core.add_membershippurchase")
@staff_permission("core.view_customer")
@staff_permission("core.collect_payment")
@require_http_methods(["GET", "POST"])
def membership_purchase(request):
    check_enabled()
    form = PurchaseForm(
        request.POST if request.method == "POST" else None,
        owner=request.user.is_superuser,
        initial={"customer": request.GET.get("customer", "")},
    )
    reviewed_offer = None
    if request.method == "POST" and form.is_valid():
        try:
            reviewed_offer = offer(actor=request.user, **form.offer_values())
            if request.POST.get("action") == "confirm":
                member = purchase(
                    actor=request.user,
                    **form.offer_values(),
                    request_key=form.cleaned_data["request_key"],
                    reviewed=form.cleaned_data["reviewed"],
                    accepted=form.cleaned_data["accepted"],
                    method_id=form.cleaned_data["method"].pk
                    if form.cleaned_data["method"]
                    else None,
                    verified_received=form.cleaned_data["verified_received"],
                    send_confirmation={"yes": True, "no": False}.get(
                        form.cleaned_data.get("send_confirmation")
                    ),
                )
                return redirect("membership_overview", pk=member.pk)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
    return render(
        request,
        "core/membership_purchase.html",
        {"form": form, "offer": display_offer(reviewed_offer)},
    )


@staff_permission("core.add_membershippurchase")
@staff_permission("core.view_customer")
@staff_permission("core.collect_payment")
@require_POST
def membership_offer(request):
    check_enabled()
    # Only product/price inputs are validated here; a preview never saves anything.
    form = PurchaseForm(request.POST, owner=request.user.is_superuser)
    for name in (
        "method",
        "accepted",
        "verified_received",
        "reviewed",
        "request_key",
        "send_confirmation",
    ):
        form.fields.pop(name, None)
    if not form.is_valid():
        return JsonResponse(
            {"error": " ".join(str(error) for errors in form.errors.values() for error in errors)},
            status=400,
        )
    try:
        data = offer(actor=request.user, **form.offer_values())
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)
    cards = PaymentMethod.objects.filter(
        customer=form.cleaned_data["customer"],
        state="active",
        reusable=True,
        environment="sandbox",
        provider_method__isnull=False,
    ).order_by("last_four", "pk")
    return JsonResponse(
        {
            "html": render_to_string(
                "core/partials/membership_offer.html",
                {"offer": display_offer(data)},
                request=request,
            ),
            "fingerprint": data["fingerprint"],
            "terms": data["terms"],
            "cards": [
                {"id": str(card.pk), "label": f"{card.brand} ending in {card.last_four}"}
                for card in cards
            ],
        }
    )


@staff_permission("core.view_membershippurchase")
@staff_permission("core.view_customer")
@require_safe
def membership_overview(request, pk):
    check_enabled()
    member = get_object_or_404(
        MembershipPurchase.objects.select_related(
            "membership", "customer", "billing_state__mandate__method"
        ),
        pk=pk,
    )
    installments = list(member.installments.select_related("invoice__sale", "cycle"))
    paid = ZERO
    for item in installments:
        item.paid = installment_paid(item)
        try:
            item.money_received = received(item.invoice.sale)
            item.operations = item.invoice.sale.operations.order_by("requested_at")
            item.remaining = max(ZERO, total(item.invoice.sale) - item.money_received)
        except MembershipInvoice.DoesNotExist:
            item.money_received, item.remaining, item.operations = ZERO, item.quote["total"], []
        paid += item.money_received
    status = membership_status(member)
    first = installments[0] if installments else None
    next_item = next((item for item in installments if not item.paid), None)
    return render(
        request,
        "core/active_membership_detail.html",
        {
            "member": member,
            "root": member.membership,
            "status": status,
            "installments": installments,
            "money_received": paid,
            "benefit_summary": summary_for(member),
            "next_item": next_item,
            "first": first,
            "today": today(),
            "current_cycle": member.membership.cycles.filter(
                starts_on__lte=today(), ends_on__gte=today()
            ).first(),
        },
    )
