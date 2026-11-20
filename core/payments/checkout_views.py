"""Two-step staff review/confirm forms. Merely opening or previewing never charges."""

import uuid
from functools import wraps

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from core.models import Booking
from core.permissions import staff_permission

from .checkout import charge_state, confirm, preview


class ReceiptForm(forms.Form):
    received_on = forms.DateField(
        required=False,
        label="Actual non-card receipt date",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="For an earlier Zelle transfer, use the bank receipt date. Leave blank for today.",
    )
    zelle_sender = forms.CharField(
        required=False, max_length=160, label="Zelle sender name/account"
    )

    def clean_received_on(self):
        from .receipts import receipt_date

        return receipt_date(self.cleaned_data.get("received_on"))


class ArrivalForm(ReceiptForm):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    reviewed_hash = forms.CharField(required=False, max_length=64, widget=forms.HiddenInput)
    children = forms.IntegerField(min_value=0, max_value=32767, label="Children attending")
    adults = forms.IntegerField(min_value=0, max_value=32767, label="Adults attending")
    babies = forms.IntegerField(min_value=0, max_value=32767, label="Babies attending")
    socks = forms.IntegerField(
        min_value=0, max_value=2147483647, label="Grip socks being purchased"
    )
    waiver_confirmed = forms.ChoiceField(
        choices=[("", "Choose Yes or No"), ("yes", "Yes"), ("no", "No")],
        label="Was a waiver signed for everyone in this booking?",
    )
    method = forms.ChoiceField(choices=[], label="Actual payment")
    cash_amount = forms.DecimalField(
        required=False, min_value=0, max_digits=14, decimal_places=2, label="Cash already received"
    )
    check_amount = forms.DecimalField(
        required=False, min_value=0, max_digits=14, decimal_places=2, label="Check already received"
    )
    zelle_amount = forms.DecimalField(
        required=False, min_value=0, max_digits=14, decimal_places=2, label="Zelle already received"
    )
    gift_card_amount = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=14,
        decimal_places=2,
        label="Physical gift-card amount presented",
    )
    zelle_verified = forms.BooleanField(
        required=False,
        label="Zelle payment was verified in the business bank account.",
        help_text="A customer screenshot alone does not confirm receipt.",
    )
    gift_card_verified = forms.BooleanField(
        required=False, label="The physical gift card has been presented and verified."
    )
    override_capacity = forms.BooleanField(
        required=False,
        label="Allow these unexpected attendees at arrival even if the configured capacity is exceeded.",
    )

    def __init__(self, *args, booking, **kwargs):
        super().__init__(*args, **kwargs)
        self.booking = booking
        self.fields["method"].choices = [
            (
                "card",
                "Charge card on file"
                if booking.expected_method == "card"
                else "No alternate payment received — charge card on file",
            ),
            ("cash", "Cash received"),
            ("check", "Check received"),
            ("zelle", "Zelle received"),
            ("gift_card", "Physical gift card presented"),
            ("split", "Split payment — record received amounts and charge the balance"),
        ]
        if charge_state(booking).comped:
            self.fields["method"].choices = [("comped", "Owner-comped booking — no payment")]

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        method = data["method"]
        if (method == "zelle" or (method == "split" and data.get("zelle_amount"))) and not data[
            "zelle_verified"
        ]:
            self.add_error(
                "zelle_verified", "Verify the received Zelle payment in the business bank account."
            )
        if (
            method == "gift_card" or (method == "split" and data.get("gift_card_amount"))
        ) and not data["gift_card_verified"]:
            self.add_error(
                "gift_card_verified",
                "Present and verify the physical gift card before recording this tender.",
            )
        data["waiver_confirmed"] = data["waiver_confirmed"] == "yes"
        data["split"] = {
            kind: str(data.get(kind + "_amount") or "0.00")
            for kind in ("cash", "check", "zelle", "gift_card")
        }
        return data


class ClosureForm(ReceiptForm):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    reviewed_hash = forms.CharField(required=False, max_length=64, widget=forms.HiddenInput)
    charge_fee = forms.ChoiceField(
        choices=[
            ("", "Choose whether to charge"),
            ("yes", "Charge the applicable fee"),
            ("no", "Do not charge a fee"),
        ],
        label="Cancellation / no-show fee",
    )
    method = forms.ChoiceField(
        required=False,
        choices=[("card", "Charge card on file"), ("gift_card", "Physical gift card presented")],
        label="Fee payment",
    )
    gift_card_verified = forms.BooleanField(
        required=False, label="The physical gift card has been presented and verified."
    )

    def __init__(self, *args, booking, kind, **kwargs):
        super().__init__(*args, **kwargs)
        if kind == "no_show":
            self.fields["method"].choices = [("card", "Charge card on file")]
        if charge_state(booking).comped:
            self.fields["charge_fee"].choices = [("no", "Owner-comped booking — no fee")]
            self.fields["charge_fee"].initial = "no"

    def clean(self):
        data = super().clean()
        data["charge_fee"] = data.get("charge_fee") == "yes"
        data["method"] = data.get("method") or "card"
        if (
            data["charge_fee"]
            and data["method"] == "gift_card"
            and not data.get("gift_card_verified")
        ):
            self.add_error(
                "gift_card_verified",
                "Present and verify the physical gift card before recording this fee tender.",
            )
        return data


def guarded(view):
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not settings.BOOKING_COMPLETION_ENABLED:
            raise Http404
        for permission in ("core.change_booking", "core.view_customer", "core.collect_payment"):
            if not request.user.has_perm(permission):
                raise PermissionDenied
        return view(request, *args, **kwargs)

    return inner


def confirm_label(kind, quote, plan):
    noun = {"arrival": "arrival", "cancellation": "cancellation", "no_show": "no show"}[kind]
    if not plan:
        return (
            f"Confirm {noun} without a fee"
            if kind != "arrival"
            else "Confirm arrival — owner-comped $0"
        )
    card = sum((p["amount"] != "0.00" and p["tender"] == "card" for p in plan))
    if card and len(plan) == 1:
        return f"Confirm {noun} and charge ${quote['total']}"
    if card:
        card_amount = next(p["amount"] for p in plan if p["tender"] == "card")
        return f"Confirm {noun}, record received funds and charge ${card_amount}"
    methods = ", ".join(p["tender"].replace("_", " ") for p in plan)
    return f"Confirm {noun} and record {methods} — ${quote['total']}"


@staff_permission("core.view_booking")
@guarded
@require_http_methods(["GET", "POST"])
def checkout(request, pk, kind="arrival"):
    booking = get_object_or_404(
        Booking.objects.select_related("customer", "session"), pk=pk, workflow="integrated_v1"
    )
    form_type = ArrivalForm if kind == "arrival" else ClosureForm
    initial = {
        "request_key": uuid.uuid4(),
        "version": booking.edit_version,
        "method": "comped" if charge_state(booking).comped else booking.expected_method,
        "zelle_sender": booking.zelle_sender,
    }
    if kind == "arrival":
        initial.update(
            {name: getattr(booking, name) for name in ("children", "adults", "babies", "socks")}
        )
    else:
        initial["method"] = "card"
    args = {"booking": booking}
    if kind != "arrival":
        args["kind"] = kind
    form = form_type(request.POST if request.method == "POST" else None, initial=initial, **args)
    reviewed = None
    label = None
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            if request.POST.get("confirm_review") == "1":
                result = confirm(
                    actor=request.user,
                    booking_id=pk,
                    kind=kind,
                    data=data,
                    request_key=data["request_key"],
                    reviewed_hash=data["reviewed_hash"],
                    confirmed=True,
                )
                queued = bool(
                    result.sale
                    and result.sale.operations.filter(
                        tender="card", state__in=["ready", "sending", "unknown", "action"]
                    ).exists()
                )
                messages.success(
                    request,
                    "Attendance/action saved. Card payment is pending provider confirmation."
                    if queued
                    else "The reviewed booking action and actual received tender were recorded.",
                )
                return redirect("booking_detail", pk=pk)
            if data["version"] != booking.edit_version:
                raise ValidationError(
                    "The booking changed. Reload it and review the current details."
                )
            _, _, quote, plan, _, digest = preview(
                actor=request.user, booking_id=pk, kind=kind, data=data
            )
            values = request.POST.copy()
            values["reviewed_hash"] = digest
            form = form_type(values, **args)
            form.is_valid()
            reviewed = {"quote": quote, "plan": plan}
            label = confirm_label(kind, quote, plan)
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
    heading = {
        "arrival": "Start arrival",
        "cancellation": "Cancel booking",
        "no_show": "Mark as no show",
    }[kind]
    return render(
        request,
        "core/booking_checkout.html",
        {
            "booking": booking,
            "form": form,
            "reviewed": reviewed,
            "confirm_label": label,
            "heading": heading,
            "kind": kind,
        },
    )


class RemainingForm(ReceiptForm):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    reviewed_hash = forms.CharField(required=False, max_length=64, widget=forms.HiddenInput)
    method = forms.ChoiceField(
        choices=[
            ("card", "Charge card on file"),
            ("cash", "Cash received"),
            ("check", "Check received"),
            ("zelle", "Zelle received"),
            ("gift_card", "Physical gift card presented"),
        ],
        label="Remaining payment",
    )
    context = forms.ChoiceField(
        choices=[
            ("", "Choose payment context"),
            ("arrival", "Customer is here reviewing the payment"),
            ("follow_up", "Following up after contacting the customer"),
        ],
        label="Payment review",
    )
    zelle_verified = forms.BooleanField(
        required=False, label="Zelle payment was verified in the business bank account."
    )
    gift_card_verified = forms.BooleanField(
        required=False, label="The physical gift card has been presented and verified."
    )

    def clean(self):
        data = super().clean()
        if data.get("method") == "zelle" and not data.get("zelle_verified"):
            self.add_error(
                "zelle_verified", "Verify the actual receipt in the business bank account."
            )
        if data.get("method") == "gift_card" and not data.get("gift_card_verified"):
            self.add_error(
                "gift_card_verified", "Verify the physical gift card before recording this tender."
            )
        return data


@staff_permission("core.view_booking")
@guarded
@require_http_methods(["GET", "POST"])
def remaining_payment(request, pk):
    from . import remainders

    booking = get_object_or_404(
        Booking.objects.select_related("customer", "session"), pk=pk, workflow="integrated_v1"
    )
    form = RemainingForm(
        request.POST if request.method == "POST" else None,
        initial={
            "request_key": uuid.uuid4(),
            "method": "card",
            "zelle_sender": booking.zelle_sender,
        },
    )
    reviewed = None
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data
        try:
            if request.POST.get("confirm_review") == "1":
                remainders.confirm(
                    actor=request.user,
                    booking_id=pk,
                    method=values["method"],
                    context=values["context"],
                    received_on=values.get("received_on"),
                    zelle_sender=values.get("zelle_sender", ""),
                    request_key=values["request_key"],
                    reviewed_hash=values["reviewed_hash"],
                    confirmed=True,
                )
                messages.success(
                    request,
                    "The reviewed remaining-payment action was recorded. Card payments require provider confirmation.",
                )
                return redirect("booking_detail", pk=pk)
            _, _, facts, digest, last_four = remainders.preview(
                actor=request.user,
                booking_id=pk,
                method=values["method"],
                context=values["context"],
                received_on=values.get("received_on"),
                zelle_sender=values.get("zelle_sender", ""),
            )
            posted = request.POST.copy()
            posted["reviewed_hash"] = digest
            form = RemainingForm(posted)
            form.is_valid()
            reviewed = {
                "amount": facts["amount"],
                "method": values["method"],
                "last_four": last_four,
            }
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
    return render(
        request,
        "core/remaining_payment.html",
        {"booking": booking, "form": form, "reviewed": reviewed},
    )


class CompedForm(forms.Form):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    comped = forms.BooleanField(
        required=False, label="Complimentary booking — all charges and cancellation fees are $0"
    )
    confirm = forms.BooleanField(label="Apply this choice and require a fresh staff setup review.")


@staff_permission("core.view_booking")
@guarded
@require_http_methods(["GET", "POST"])
def complimentary(request, pk):
    from .comped import set_comped

    if not request.user.is_superuser:
        raise PermissionDenied
    booking = get_object_or_404(
        Booking.objects.select_related("session"), pk=pk, workflow="integrated_v1"
    )
    form = CompedForm(
        request.POST if request.method == "POST" else None,
        initial={"version": booking.edit_version, "comped": charge_state(booking).comped},
    )
    if request.method == "POST" and form.is_valid():
        try:
            set_comped(
                actor=request.user,
                booking_id=pk,
                version=form.cleaned_data["version"],
                comped=form.cleaned_data["comped"],
            )
            messages.success(
                request,
                "Complimentary status saved. Review and confirm the booking setup; waiver coverage is still required.",
            )
            return redirect("booking_detail", pk=pk)
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
    return render(request, "core/booking_comped.html", {"booking": booking, "form": form})
