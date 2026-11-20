"""Limited shared signing pages and permission-checked staff waiver records."""

import uuid
from functools import wraps

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from core.forms import normalize_phone
from core.models import Booking
from core.pagination import paginate
from core.permissions import staff_permission
from core.public_booking_views import current, limit, save

from .forms import SignatureForm
from .models import WaiverSignature
from .services import (
    VERSION,
    approved_version,
    create_share,
    share_for_token,
    sign,
    signed_evidence,
)
from .storage import EvidenceUnavailable


def enabled_view(view):
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not settings.WAIVER_ENABLED:
            raise Http404
        return view(request, *args, **kwargs)

    return inner


def signing_form(request, *, flow=None, share_token=None):
    version = approved_version()
    share = share_for_token(share_token) if share_token else None
    form = SignatureForm(
        request.POST if request.method == "POST" else None,
        initial={
            "request_key": uuid.uuid4(),
            "version": version.pk,
            "text_hash": version.text_hash,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            limit(request, "waiver-signature", 10)
            if flow and (
                request.POST.get("wizard_key") != flow["key"]
                or request.POST.get("wizard_stage") != flow["stage"]
            ):
                raise ValidationError("The booking changed. Return to the current booking page.")
            signature = sign(
                data=request.POST,
                flow=flow,
                share_token=share_token,
                ip=request.META.get("REMOTE_ADDR") or None,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            if flow:
                ids = flow.setdefault("waiver_signatures", [])
                if str(signature.pk) not in ids:
                    ids.append(str(signature.pk))
                save(request, flow)
            messages.success(request, "Thank you. Your electronic waiver has been saved.")
            return (
                redirect("shared_waiver", token=share_token)
                if share
                else redirect("customer_waiver")
            )
        except EvidenceUnavailable:
            form.add_error(
                None,
                "We could not confirm that your signed waiver was saved. Please keep this page open and try again, or call/text 848-238-5147 for assistance.",
            )
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
    return render(
        request,
        "core/waivers/sign.html",
        {
            "form": form,
            "version": version,
            "legal_html": version.legal_html,
            "appointment": share.booking.session.starts_at if share else None,
            "shared": share is not None,
            "flow": flow,
        },
    )


@enabled_view
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters()
def public_sign(request):
    try:
        flow = current(request)
        if flow.get("workflow") != "integrated_v1" or not flow.get("details"):
            raise ValidationError("Complete your customer and session details before signing.")
        return signing_form(request, flow=flow)
    except ValidationError as error:
        return render(
            request,
            "core/waivers/unavailable.html",
            {"reason": " ".join(error.messages)},
            status=400,
        )


@enabled_view
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters()
def shared_sign(request, token):
    try:
        return signing_form(request, share_token=token)
    except ValidationError as error:
        return render(
            request,
            "core/waivers/unavailable.html",
            {"reason": " ".join(error.messages)},
            status=410,
        )


class WaiverFilters(forms.Form):
    q = forms.CharField(
        required=False, max_length=120, label="Customer, signer, minor, phone or email"
    )
    status = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All statuses"),
            ("valid", "Current and unexpired"),
            ("expired", "Expired"),
            ("superseded", "Earlier version"),
            ("pending", "Evidence pending"),
            ("removed", "Evidence removed"),
        ],
    )
    customer = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    after = forms.DateField(
        required=False, label="Signed from", widget=forms.DateInput(attrs={"type": "date"})
    )
    before = forms.DateField(
        required=False, label="Signed through", widget=forms.DateInput(attrs={"type": "date"})
    )

    def clean(self):
        data = super().clean()
        if data.get("after") and data.get("before") and data["after"] > data["before"]:
            raise forms.ValidationError("The end date must be on or after the start date.")
        return data


def staff_access(request):
    if not request.user.has_perm("core.view_customer") or not request.user.has_perm(
        "core.view_booking"
    ):
        raise PermissionDenied


@staff_permission("core.view_waiversignature")
@enabled_view
@require_safe
def waivers(request):
    staff_access(request)
    records = WaiverSignature.objects.select_related("version").order_by("-signed_at", "-pk")
    form = WaiverFilters(request.GET)
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            query = data["q"].strip()
            matches = (
                Q(signer_name__icontains=query)
                | Q(signer_email__icontains=query)
                | Q(minors__icontains=query)
                | Q(customer_links__customer__last_name__icontains=query)
                | Q(booking_links__booking__customer__last_name__icontains=query)
            )
            try:
                matches |= Q(signer_phone=normalize_phone(query))
            except ValidationError:
                pass
            records = records.filter(matches)
        if data["customer"]:
            records = records.filter(
                Q(customer_links__customer_id=data["customer"])
                | Q(booking_links__booking__customer_id=data["customer"])
            )
        if data["status"] == "valid":
            records = records.filter(
                state="signed", version_id=VERSION, valid_until__gt=timezone.now()
            )
        elif data["status"] == "expired":
            records = records.filter(valid_until__lte=timezone.now())
        elif data["status"] == "superseded":
            records = records.exclude(version_id=VERSION)
        elif data["status"] == "pending":
            records = records.filter(state="pending")
        elif data["status"] == "removed":
            records = records.filter(state__in=["deleting", "deleted"])
        if data["after"]:
            records = records.filter(signed_at__date__gte=data["after"])
        if data["before"]:
            records = records.filter(signed_at__date__lte=data["before"])
    else:
        records = records.none()
    return render(
        request,
        "core/waivers/list.html",
        {
            "form": form,
            "signatures": paginate(request, records.distinct()),
            "waiver_now": timezone.now(),
            "current_version": VERSION,
        },
    )


@staff_permission("core.view_waiversignature")
@enabled_view
@require_safe
def waiver_detail(request, pk):
    staff_access(request)
    signature = get_object_or_404(WaiverSignature.objects.select_related("version"), pk=pk)
    return render(
        request,
        "core/waivers/detail.html",
        {"signature": signature, "waiver_now": timezone.now(), "current_version": VERSION},
    )


@staff_permission("core.view_signed_waiver")
@staff_permission("core.view_waiversignature")
@enabled_view
@require_safe
def evidence(request, pk):
    staff_access(request)
    try:
        data = signed_evidence(actor=request.user, signature_id=pk)
    except WaiverSignature.DoesNotExist:
        raise Http404 from None
    except EvidenceUnavailable:
        return render(
            request,
            "core/waivers/unavailable.html",
            {
                "reason": "The signed file is temporarily unavailable. No unverified document was returned."
            },
            status=503,
        )
    response = HttpResponse(data, content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = f'inline; filename="MonkeyDo-waiver-{pk}.html"'
    response["Content-Security-Policy"] = (
        "sandbox; default-src 'none'; style-src 'unsafe-inline'; form-action 'none'"
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Frame-Options"] = "DENY"
    return response


@staff_permission("core.change_booking")
@staff_permission("core.view_booking")
@enabled_view
@require_POST
def share_create(request, booking_id):
    try:
        link, token = create_share(actor=request.user, booking_id=booking_id)
    except (ValidationError, Booking.DoesNotExist):
        raise Http404 from None
    return render(
        request,
        "core/waivers/share.html",
        {
            "booking": link.booking,
            "share_url": request.build_absolute_uri(
                reverse("shared_waiver", kwargs={"token": token})
            ),
        },
    )


@enabled_view
@require_safe
def unsigned_pdf(request):
    path = settings.BASE_DIR / "docs" / "waivers" / "source" / "MD Waiver (1).pdf"
    return FileResponse(
        path.open("rb"),
        as_attachment=True,
        filename="MonkeyDo-unsigned-waiver.pdf",
        content_type="application/pdf",
    )
