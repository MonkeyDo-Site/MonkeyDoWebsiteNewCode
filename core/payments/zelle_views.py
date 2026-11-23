"""Explicit recording of bank receipts and owner-confirmed manual refunds."""

import uuid
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from core.models import Booking
from core.permissions import staff_permission

from . import zelle
from .checkout_views import guarded


class ZelleReceiptForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    value = forms.DecimalField(
        min_value=Decimal(".01"), max_digits=14, decimal_places=2, label="Zelle amount received"
    )
    received_on = forms.DateField(
        required=False,
        label="Bank receipt date",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Leave blank for today.",
    )
    sender_name = forms.CharField(max_length=160, label="Zelle sender name/account")
    verified = forms.BooleanField(label="I verified this receipt in the business bank account.")


class ZelleRefundForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    reviewed_amount = forms.DecimalField(
        min_value=Decimal(".01"), max_digits=14, decimal_places=2, widget=forms.HiddenInput
    )
    completed_on = forms.DateField(
        required=False,
        label="Date returned",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Leave blank for today.",
    )
    confirmed = forms.BooleanField(
        label="I have actually returned this amount to the customer through Zelle."
    )


@staff_permission("core.view_booking")
@guarded
@require_http_methods(["GET", "POST"])
def receipt(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related("customer"), pk=pk, workflow="integrated_v1"
    )
    form = ZelleReceiptForm(
        request.POST or None,
        initial={"request_key": uuid.uuid4(), "sender_name": booking.zelle_sender},
    )
    if request.method == "POST" and form.is_valid():
        try:
            zelle.record_receipt(actor=request.user, booking_id=pk, **form.cleaned_data)
            if request.headers.get("Accept") == "application/json":
                return JsonResponse(
                    {"saved": True, "received": str(zelle.facts(booking)["received"])}
                )
            messages.success(
                request, "Verified Zelle receipt recorded. Arrival has not been marked."
            )
            return redirect("booking_detail", pk=pk)
        except ValidationError as error:
            form.add_error(None, error)
    if request.headers.get("Accept") == "application/json":
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    return render(
        request,
        "core/zelle_record.html",
        {
            "booking": booking,
            "form": form,
            "heading": "Record Zelle received",
            "zelle": zelle.facts(booking),
        },
    )


@staff_permission("core.view_booking")
@guarded
@require_http_methods(["GET", "POST"])
def refund(request, pk):
    from django.core.exceptions import PermissionDenied

    if not request.user.is_superuser:
        raise PermissionDenied
    booking = get_object_or_404(
        Booking.objects.select_related("customer"), pk=pk, workflow="integrated_v1"
    )
    facts = zelle.facts(booking)
    form = ZelleRefundForm(
        request.POST or None,
        initial={"request_key": uuid.uuid4(), "reviewed_amount": facts["refund_due"]},
    )
    if request.method == "POST" and form.is_valid():
        try:
            zelle.complete_refund(actor=request.user, booking_id=pk, **form.cleaned_data)
            messages.success(
                request, "Completed Zelle refund recorded. The Dashboard notice is resolved."
            )
            return redirect("booking_detail", pk=pk)
        except ValidationError as error:
            form.add_error(None, error)
    return render(
        request,
        "core/zelle_record.html",
        {
            "booking": booking,
            "form": form,
            "heading": "Record completed Zelle refund",
            "zelle": facts,
            "refund": True,
        },
    )
