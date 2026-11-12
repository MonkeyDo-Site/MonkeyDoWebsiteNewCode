from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import BooleanField, Case, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from .booking_forms import PricingPolicyForm, TestBookingForm, TimingForm
from .booking_management import (
    create_test_booking,
    edit_test_booking,
    move_test_booking,
    release_test_booking,
)
from .models import AuditEvent, Booking, Customer, PricingPolicy
from .name_matching import match_rank, name_candidates
from .permissions import staff_permission


def form_error(form, error):
    form.add_error(None, " ".join(error.messages))


@staff_permission("core.view_booking")
@require_safe
def bookings(request):
    query = request.GET.get("q", "").strip()[:120]
    rows = Booking.objects.select_related("customer", "session").order_by(
        "-session__starts_at", "-pk"
    )
    exact, possible = name_candidates(query) if query else ([], [])
    if query:
        rows = rows.filter(
            Q(customer__last_name__icontains=query)
            | Q(customer__phone__icontains=query)
            | Q(customer_id__in=exact + possible)
        ).order_by(match_rank("customer_id", exact, possible), "-session__starts_at", "-pk")
    rows = rows.annotate(
        possible_name_match=Case(
            When(customer_id__in=possible, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
    )
    return render(
        request,
        "core/bookings.html",
        {"bookings": Paginator(rows, 25).get_page(request.GET.get("page")), "query": query},
    )


@staff_permission("core.view_booking")
@require_safe
def booking_detail(request, pk):
    booking = get_object_or_404(Booking.objects.select_related("customer", "session"), pk=pk)
    return render(
        request,
        "core/booking_detail.html",
        {
            "booking": booking,
            "quote": booking.quotes.first(),
            "quotes": booking.quotes.select_related("policy", "actor"),
            "history": AuditEvent.objects.filter(
                record_type="booking", record_id=str(booking.reference)
            ).select_related("actor"),
        },
    )


@staff_permission("core.view_booking")
@staff_permission("core.add_booking")
@staff_permission("core.view_customer")
@require_http_methods(["GET", "POST"])
def booking_create(request):
    customer = None
    if (
        request.GET.get("customer", "").isascii()
        and request.GET.get("customer", "").isdigit()
        and len(request.GET["customer"]) <= 18
    ):
        customer = Customer.objects.filter(pk=int(request.GET["customer"])).first()
    form = TestBookingForm(
        request.POST if request.method == "POST" else None,
        owner=request.user.is_superuser,
        customer=customer,
    )
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        data["session_id"] = data.pop("session").pk
        try:
            booking = create_test_booking(actor=request.user, **data)
        except ValidationError as exc:
            form_error(form, exc)
        else:
            messages.success(
                request,
                "Test reservation saved with its price snapshot. Setup is pending; no payment, signature, or confirmation email was recorded.",
            )
            return redirect("booking_detail", pk=booking.pk)
    return render(
        request, "core/booking_form.html", {"form": form, "heading": "Create test booking"}
    )


@staff_permission("core.view_booking")
@staff_permission("core.change_booking")
@require_http_methods(["GET", "POST"])
def booking_edit(request, pk):
    booking = get_object_or_404(Booking.objects.select_related("customer", "session"), pk=pk)
    form = TestBookingForm(
        request.POST if request.method == "POST" else None,
        owner=request.user.is_superuser,
        booking=booking,
    )
    if request.method == "POST" and form.is_valid():
        try:
            edit_test_booking(actor=request.user, booking_id=pk, **form.cleaned_data)
        except ValidationError as exc:
            form_error(form, exc)
        else:
            messages.success(
                request,
                "Attendees and expected payment method updated using the saved pricing policy. No money was collected.",
            )
            return redirect("booking_detail", pk=pk)
    return render(
        request,
        "core/booking_form.html",
        {"form": form, "heading": "Edit test booking", "booking": booking},
    )


@staff_permission("core.view_booking")
@staff_permission("core.change_booking")
@require_http_methods(["GET", "POST"])
def booking_move(request, pk):
    booking = get_object_or_404(Booking.objects.select_related("customer", "session"), pk=pk)
    form = TimingForm(
        request.POST if request.method == "POST" else None,
        owner=request.user.is_superuser,
        booking=booking,
    )
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        data["session_id"] = data.pop("session").pk
        try:
            move_test_booking(actor=request.user, booking_id=pk, **data)
        except ValidationError as exc:
            form_error(form, exc)
        else:
            messages.success(request, "Timing updated. The saved quote was not repriced.")
            return redirect("booking_detail", pk=pk)
    return render(
        request,
        "core/booking_form.html",
        {"form": form, "heading": "Change timing", "booking": booking},
    )


@staff_permission("core.view_booking")
@staff_permission("core.change_booking")
@require_POST
def booking_release(request, pk):
    get_object_or_404(Booking, pk=pk)
    try:
        version = int(request.POST.get("version", ""))
        release_test_booking(actor=request.user, booking_id=pk, version=version)
    except ValueError:
        messages.error(request, "Reload the record before cancelling it.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(
            request,
            "Test booking cancelled. No cancellation fee was recorded or charged.",
        )
    return redirect("booking_detail", pk=pk)


@staff_permission("core.add_pricingpolicy")
@require_http_methods(["GET", "POST"])
def pricing_settings(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    policy = PricingPolicy.objects.first()
    form = PricingPolicyForm(request.POST if request.method == "POST" else None, policy=policy)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            new = form.save(commit=False)
            new.actor = request.user
            new.save()
            AuditEvent.objects.create(
                actor=request.user,
                action="pricing.policy_created",
                record_type="pricing_policy",
                record_id=str(new.pk),
                changes={"previous_policy": policy.pk if policy else None, "test_mode": True},
            )
        messages.success(
            request,
            "New staging pricing version saved. Existing quotes retain their original rates.",
        )
        return redirect("pricing_settings")
    return render(request, "core/pricing_settings.html", {"form": form, "policy": policy})
