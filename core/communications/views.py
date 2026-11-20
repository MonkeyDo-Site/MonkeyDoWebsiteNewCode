"""Permission-checked message history and explicit booking-only resend."""

import uuid
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

from .models import MessageDelivery
from .services import resend_confirmation


def enabled_view(view):
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not settings.BOOKING_EMAIL_ENABLED:
            raise Http404
        if not request.user.has_perm("core.view_customer") or not request.user.has_perm(
            "core.view_booking"
        ):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return inner


class MessageFilters(forms.Form):
    q = forms.CharField(required=False, max_length=120, label="Family, phone or email")
    state = forms.ChoiceField(
        required=False,
        choices=[("", "All statuses")] + list(MessageDelivery._meta.get_field("state").choices),
        label="Status",
    )
    booking = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    after = forms.DateField(
        required=False, label="Created from", widget=forms.DateInput(attrs={"type": "date"})
    )
    before = forms.DateField(
        required=False, label="Created through", widget=forms.DateInput(attrs={"type": "date"})
    )

    def clean(self):
        data = super().clean()
        if data.get("after") and data.get("before") and data["after"] > data["before"]:
            raise forms.ValidationError("The end date must be on or after the start date.")
        return data


@staff_permission("core.view_messagedelivery")
@enabled_view
@require_safe
def message_list(request):
    records = MessageDelivery.objects.select_related("customer", "booking").order_by(
        "-created_at", "-pk"
    )
    if not request.user.is_superuser:
        records = records.exclude(kind__in=["payment_issue", "backup_alert", "email_issue"])
    form = MessageFilters(request.GET)
    possible = []
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            q = data["q"].strip()
            exact, possible = name_candidates(q)
            digits = phone_search_digits(q)
            matches = (
                Q(customer__last_name__icontains=q)
                | Q(recipient__icontains=q)
                | Q(customer__email__icontains=q)
                | Q(customer__previous_email__icontains=q)
                | Q(customer_id__in=exact + possible)
            )
            if digits:
                matches |= Q(customer__phone__contains=digits) | Q(
                    customer__previous_phone__contains=digits
                )
            records = records.filter(matches).order_by(
                match_rank("customer_id", exact, possible), "-created_at", "-pk"
            )
        if data["state"]:
            records = records.filter(state=data["state"])
        if data["booking"]:
            records = records.filter(booking_id=data["booking"])
        if data["after"]:
            records = records.filter(created_at__date__gte=data["after"])
        if data["before"]:
            records = records.filter(created_at__date__lte=data["before"])
    else:
        records = records.none()
    page = paginate(request, records)
    for item in page:
        item.possible_name = item.customer_id in possible
    return render(request, "core/messages/list.html", {"form": form, "deliveries": page})


class ResendForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    confirm = forms.BooleanField(
        label="Send this booking confirmation again to the customer’s current email address."
    )


@staff_permission("core.view_messagedelivery")
@enabled_view
@require_http_methods(["GET", "POST"])
def message_detail(request, pk):
    message = get_object_or_404(
        MessageDelivery.objects.select_related("customer", "booking"), pk=pk
    )
    if (
        message.kind in {"payment_issue", "backup_alert", "email_issue"}
        and not request.user.is_superuser
    ):
        raise PermissionDenied
    can_resend = bool(
        message.booking_id
        and message.kind in {"booking_confirmation", "booking_waiver"}
        and request.user.has_perm("core.change_booking")
    )
    form = ResendForm(
        request.POST if request.method == "POST" else None, initial={"request_key": uuid.uuid4()}
    )
    if request.method == "POST":
        if not can_resend:
            raise PermissionDenied
        if form.is_valid():
            try:
                queued = resend_confirmation(
                    actor=request.user,
                    message_id=message.pk,
                    request_key=form.cleaned_data["request_key"],
                )
                messages.success(
                    request,
                    "A confirmation attempt is queued. Its current delivery status appears below.",
                )
                return redirect("message_detail", pk=queued.pk)
            except ValidationError as error:
                form.add_error(None, " ".join(error.messages))
    return render(
        request,
        "core/messages/detail.html",
        {"delivery": message, "form": form, "can_resend": can_resend},
    )
