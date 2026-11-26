import uuid

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from .booking_forms import PricingPolicyForm, TestBookingForm, TimingForm, session_date_picker
from .booking_management import (
    create_test_booking,
    edit_test_booking,
    move_test_booking,
    release_test_booking,
)
from .models import AuditEvent, Booking, Customer, PricingPolicy
from .pagination import paginate
from .permissions import staff_permission
from .session_blocks import booking_has_blocks


def form_error(form, error):
    form.add_error(None, " ".join(error.messages))


@staff_permission("core.view_booking")
@require_safe
def bookings(request):
    from .booking_filters import booking_context

    context = booking_context(request)
    context["bookings"] = paginate(request, context.pop("rows"))
    return render(request, "core/bookings.html", context)


@staff_permission("core.view_booking")
@require_safe
def booking_detail(request, pk):
    booking = get_object_or_404(Booking.objects.select_related("customer", "session"), pk=pk)
    waiver_context = {}
    payment_context = {}
    if (
        settings.BOOKING_COMPLETION_ENABLED
        and request.user.has_perm("core.view_paymentoperation")
        and booking.workflow == "integrated_v1"
    ):
        from .payments.checkout import summary

        payment_context["payment_summary"] = summary(booking)
    if settings.WAIVER_ENABLED and request.user.has_perm("core.view_waiversignature"):
        from .waivers.forms import NamedPaperWaiverForm

        waiver_context = {
            "waiver_links": booking.waiver_links.select_related("signature"),
            "paper_form": NamedPaperWaiverForm(initial={"request_key": uuid.uuid4()}),
            "paper_waivers": booking.customer.paper_waivers.all().order_by("-signed_at"),
        }
    from .waivers.paper import active_customer_waivers

    actual_breakdown = None
    checkout = booking.checkouts.select_related("sale").order_by("-created_at").first()
    if checkout and checkout.sale:
        from .payments.presentation import invoice_breakdown

        actual_breakdown = invoice_breakdown(checkout.sale)
    from django.core.paginator import Paginator
    from django.db.models import Q

    from core.forms import CommentForm, phone_search_digits

    from .price_adjustments import booking_price_adjustment

    comments = (
        booking.comments.select_related("author")
        if request.user.has_perm("core.view_customercomment")
        and request.user.has_perm("core.view_customer")
        else booking.comments.none()
    )
    comment_query = request.GET.get("comment_q", "").strip()[:120]
    if comment_query:
        comment_filter = Q(body__icontains=comment_query)
        digits = phone_search_digits(comment_query)
        if digits:
            comment_filter |= Q(search_digits__contains=digits)
        comments = comments.filter(comment_filter)
    comment_page = Paginator(comments, 20).get_page(request.GET.get("comments_page"))
    latest_quote = booking.quotes.first()
    booking_adjustment = (
        booking_price_adjustment(booking, actual_breakdown or latest_quote.snapshot)
        if latest_quote
        else None
    )
    history = AuditEvent.objects.filter(
        record_type="booking", record_id=str(booking.reference)
    ).select_related("actor")
    if not (
        request.user.has_perm("core.view_customercomment")
        and request.user.has_perm("core.view_customer")
    ):
        history = history.exclude(action__in=["booking.comment_added", "booking.comment_updated"])
    return render(
        request,
        "core/booking_detail.html",
        {
            "booking": booking,
            "booking_comments": comment_page,
            "booking_comment_query": comment_query,
            "booking_comment_form": CommentForm(),
            "actual_breakdown": actual_breakdown,
            "booking_adjustment": booking_adjustment,
            "active_waivers": active_customer_waivers(booking)
            if settings.WAIVER_ENABLED and request.user.has_perm("core.view_waiversignature")
            else [],
            **waiver_context,
            **payment_context,
            "booking_messages": booking.messages.exclude(
                kind__in=["payment_issue", "email_issue", "backup_alert"]
            ).order_by("-created_at")[:5]
            if settings.BOOKING_EMAIL_ENABLED and request.user.has_perm("core.view_messagedelivery")
            else [],
            "quote": booking.quotes.first(),
            "quotes": booking.quotes.select_related("policy", "actor"),
            "has_reservation_blocks": booking_has_blocks(booking),
            "history": history,
        },
    )


@staff_permission("core.view_booking")
@staff_permission("core.add_booking")
@staff_permission("core.view_customer")
@require_http_methods(["GET", "POST"])
def booking_create(request):
    if settings.BOOKING_COMPLETION_ENABLED:
        from .payments.staff_create import page

        return page(request)
    customer = None
    if (
        request.GET.get("customer", "").isascii()
        and request.GET.get("customer", "").isdigit()
        and len(request.GET["customer"]) <= 18
    ):
        customer = Customer.objects.filter(pk=int(request.GET["customer"])).first()
    posted = request.POST if request.method == "POST" else None
    form = TestBookingForm(posted, owner=request.user.is_superuser, customer=customer)
    if (
        request.method == "GET"
        and request.GET.get("session", "").isdigit()
        and len(request.GET["session"]) < 19
    ):
        form.initial["session"] = request.GET["session"]
        session_date_picker(form)
    if request.method == "POST" and request.POST.get("load_sessions") != "1" and form.is_valid():
        data = dict(form.cleaned_data)
        data["workflow"] = "integrated_v1" if settings.BOOKING_COMPLETION_ENABLED else "legacy_test"
        data.pop("session_date", None)
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
    from .booking_estimates import amount_reviewed, edit_estimate

    estimate = None
    show_reminder = False
    if request.method == "POST" and request.POST.get("load_sessions") != "1" and form.is_valid():
        try:
            estimate = edit_estimate(booking, form.cleaned_data)
            if estimate["amount_changed"] and not amount_reviewed(
                form.cleaned_data.get("estimate_token", ""), estimate
            ):
                show_reminder = True
                posted = request.POST.copy()
                posted["estimate_token"] = estimate["token"]
                form = TestBookingForm(posted, owner=request.user.is_superuser, booking=booking)
            else:
                data = dict(form.cleaned_data)
                data.pop("estimate_token", None)
                data.pop("session_date", None)
                edit_test_booking(actor=request.user, booking_id=pk, **data)
                messages.success(
                    request,
                    "Booking updated using the saved pricing policy. No money was collected.",
                )
                return redirect("booking_detail", pk=pk)
        except ValidationError as exc:
            form_error(form, exc)
            form.show_supervised_exception = (
                request.user.is_superuser
                and getattr(exc, "code", None) == "supervised_exception_required"
            )
    if estimate is None and booking.quotes.first():
        saved = booking.quotes.first()
        from .price_adjustments import booking_price_adjustment

        estimate = {
            "quote": saved.snapshot,
            "original_total": saved.snapshot["total"],
            "adjustment": booking_price_adjustment(booking, saved.snapshot),
        }
    return render(
        request,
        "core/booking_form.html",
        {
            "form": form,
            "heading": "Edit booking"
            if booking.workflow == "integrated_v1"
            else "Edit test booking",
            "booking": booking,
            "estimate": estimate,
            "show_payment_reminder": show_reminder,
        },
    )


@staff_permission("core.view_booking")
@staff_permission("core.change_booking")
@require_POST
def booking_estimate(request, pk):
    from django.http import JsonResponse
    from django.template.loader import render_to_string

    from .booking_estimates import edit_estimate

    booking = get_object_or_404(Booking, pk=pk)
    form = TestBookingForm(request.POST, owner=request.user.is_superuser, booking=booking)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    try:
        estimate = edit_estimate(booking, form.cleaned_data)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)
    return JsonResponse(
        {
            "html": render_to_string(
                "core/quote_items.html",
                {"data": estimate["quote"], "adjustment": estimate["adjustment"]},
                request=request,
            ),
            "total": estimate["quote"]["total"],
            "original_total": estimate["original_total"],
            "amount_changed": estimate["amount_changed"],
            "token": estimate["token"],
        },
        headers={"Cache-Control": "private, no-store"},
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
    if request.method == "POST" and request.POST.get("load_sessions") != "1" and form.is_valid():
        data = dict(form.cleaned_data)
        data.pop("session_date", None)
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
        {"form": form, "heading": "Change timing", "booking": booking, "timing_only": True},
    )


@staff_permission("core.view_booking")
@staff_permission("core.change_booking")
@require_POST
def booking_release(request, pk):
    booking = get_object_or_404(Booking.objects.select_related("customer", "session"), pk=pk)
    if request.POST.get("confirm_cancel") != "1":
        return render(
            request,
            "core/booking_cancel_confirm.html",
            {"booking": booking, "has_reservation_blocks": booking_has_blocks(booking)},
        )
    try:
        version = int(request.POST.get("version", ""))
        release_test_booking(
            actor=request.user,
            booking_id=pk,
            version=version,
            reopen_affected_sessions=request.POST.get("reopen_affected_sessions") == "on",
        )
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
    if request.method == "POST" and request.POST.get("load_sessions") != "1" and form.is_valid():
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


@staff_permission("core.view_booking")
@require_safe
def dated_sessions(request):
    from django import forms
    from django.http import JsonResponse

    from .booking_forms import selectable_sessions

    if not (
        request.user.has_perm("core.add_booking") or request.user.has_perm("core.change_booking")
    ):
        raise PermissionDenied
    try:
        day = forms.DateField().clean(request.GET.get("day"))
    except forms.ValidationError:
        return JsonResponse({"error": "Choose a valid session date."}, status=400)
    booking = None
    if request.GET.get("booking", "").isdigit() and len(request.GET["booking"]) < 19:
        if not request.user.has_perm("core.change_booking"):
            raise PermissionDenied
        booking = get_object_or_404(Booking, pk=request.GET["booking"])
    rows = selectable_sessions(booking).filter(starts_at__date=day)

    def item(row):
        from .booking_forms import session_capacity_summary

        return {
            "id": row.pk,
            "label": str(row),
            "play_mode": row.play_mode,
            "supervised_capacity": row.supervised_capacity,
            "started": row.starts_at <= timezone.now(),
            "capacity": session_capacity_summary(row, booking),
        }

    return JsonResponse(
        {"sessions": [item(row) for row in rows]},
        headers={"Cache-Control": "private, no-store"},
    )
