"""Staff-safe financial history and owner-only read-only-provider reconciliation."""

from functools import wraps

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from core.forms import phone_search_digits
from core.name_matching import match_rank, name_candidates
from core.pagination import paginate
from core.permissions import staff_permission

from .gateway import ProviderFailure
from .models import PaymentOperation, PaymentSetup
from .operations import reconcile
from .setup import reconcile_setup


def enabled_view(view):
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not settings.PAYMENT_SANDBOX_ENABLED:
            raise Http404
        if not request.user.has_perm("core.view_customer"):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return inner


class PaymentFilters(forms.Form):
    q = forms.CharField(max_length=120, required=False, label="Family, phone or email")
    state = forms.MultipleChoiceField(
        required=False,
        choices=PaymentOperation.State.choices,
        widget=forms.CheckboxSelectMultiple,
        label="Status",
    )
    after = forms.DateField(
        required=False, label="Requested from", widget=forms.DateInput(attrs={"type": "date"})
    )
    before = forms.DateField(
        required=False, label="Requested through", widget=forms.DateInput(attrs={"type": "date"})
    )

    def clean(self):
        data = super().clean()
        if data.get("after") and data.get("before") and data["before"] < data["after"]:
            raise forms.ValidationError("The end date must be on or after the start date.")
        return data


@staff_permission("core.view_paymentoperation")
@enabled_view
@require_safe
def payments(request):
    records = PaymentOperation.objects.select_related("sale__customer", "sale__booking").order_by(
        "-requested_at", "-pk"
    )
    form = PaymentFilters(request.GET)
    possible = []
    if form.is_valid():
        data = form.cleaned_data
        query = data["q"].strip()
        if query:
            exact, possible = name_candidates(query)
            digits = phone_search_digits(query)
            match = (
                Q(sale__customer__last_name__icontains=query)
                | Q(sale__customer__email__icontains=query)
                | Q(sale__customer_id__in=exact + possible)
            )
            if digits:
                match |= Q(sale__customer__phone__contains=digits) | Q(
                    sale__customer__previous_phone__contains=digits
                )
            records = records.filter(match).order_by(
                match_rank("sale__customer_id", exact, possible), "-requested_at", "-pk"
            )
        if data["state"]:
            records = records.filter(state__in=data["state"])
        if data["after"]:
            records = records.filter(requested_at__date__gte=data["after"])
        if data["before"]:
            records = records.filter(requested_at__date__lte=data["before"])
    else:
        records = records.none()
    page = paginate(request, records)
    for item in page:
        item.possible_name = item.sale.customer_id in possible
    setups = (
        PaymentSetup.objects.filter(state__in=["unknown", "customer_sending", "method_sending"])
        .select_related("customer")
        .order_by("-created_at")[:10]
        if request.user.is_superuser
        else []
    )
    return render(
        request, "core/payments.html", {"operations": page, "form": form, "setups": setups}
    )


class ReconcileForm(forms.Form):
    provider_reference = forms.RegexField(
        r"^[1-9][0-9]{0,19}$",
        max_length=20,
        required=False,
        label="Banquest transaction reference (if not already recorded)",
    )


@staff_permission("core.view_paymentoperation")
@enabled_view
@require_http_methods(["GET", "POST"])
def payment_detail(request, pk):
    operation = get_object_or_404(
        PaymentOperation.objects.select_related("sale__customer", "sale__booking", "original"),
        pk=pk,
    )
    form = ReconcileForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if not request.user.is_superuser:
            raise PermissionDenied
        if form.is_valid():
            try:
                result = reconcile(
                    operation_id=operation.pk,
                    actor=request.user,
                    provider_reference=form.cleaned_data["provider_reference"] or None,
                )
                if result.state == "succeeded":
                    messages.success(request, "The provider result is verified and recorded.")
                else:
                    messages.warning(
                        request, "The outcome still needs review. No new charge or refund was sent."
                    )
                return redirect("payment_detail", pk=operation.pk)
            except (ValidationError, ProviderFailure):
                form.add_error(
                    None,
                    "The result could not be confirmed. Review the original provider transaction before any further payment.",
                )
    return render(request, "core/payment_detail.html", {"operation": operation, "form": form})


@staff_permission("core.view_paymentoperation")
@enabled_view
@require_http_methods(["GET", "POST"])
def card_setup_detail(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    setup = get_object_or_404(PaymentSetup.objects.select_related("customer", "method"), pk=pk)
    error = None
    if request.method == "POST":
        try:
            reconcile_setup(actor=request.user, setup_id=pk)
            messages.success(request, "Saved-card metadata was reconciled. No payment was charged.")
            return redirect("card_setup_detail", pk=pk)
        except (ValidationError, ProviderFailure):
            error = (
                "Card setup still needs provider review. No nonce exchange or charge was repeated."
            )
    return render(request, "core/payment_setup_detail.html", {"setup": setup, "error": error})
