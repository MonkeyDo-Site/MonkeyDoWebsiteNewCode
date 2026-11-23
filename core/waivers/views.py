"""Limited shared signing pages and permission-checked staff waiver records."""

import hashlib
import uuid
from functools import wraps

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import BooleanField, Case, Q, Value, When
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from core.booking_progress import progress
from core.forms import phone_search_digits
from core.models import Booking
from core.name_matching import name_candidates
from core.pagination import paginate
from core.permissions import staff_permission
from core.public_booking_views import current, limit, save

from .coverage_forms import CoverageConfirmationForm, current_signatures
from .forms import SignatureForm
from .models import WaiverSignature
from .services import (
    COVERAGE_VERSIONS,
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
        response = view(request, *args, **kwargs)
        add_never_cache_headers(response)
        return response

    return inner


def signing_form(request, *, flow=None, share_token=None):
    if settings.RECOVERY_HOLD:
        return render(request, "core/booking_paused.html", status=503)
    version = approved_version()
    share = share_for_token(share_token) if share_token else None
    if share and request.method == "GET" and request.GET.get("signed"):
        try:
            share.booking.waiver_links.select_related("signature").get(
                signature_id=request.GET["signed"],
                signature__state="signed",
                signature__flow_hash=hashlib.sha256(
                    ("shared:" + str(share.pk)).encode()
                ).hexdigest(),
            )
        except (ValueError, ValidationError, share.booking.waiver_links.model.DoesNotExist):
            raise Http404 from None
        return render(
            request,
            "core/waivers/shared_complete.html",
            {"appointment": share.booking.session.starts_at},
        )
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
                flow["last_waiver_signature"] = str(signature.pk)
                flow["stage"] = "waiver"
                save(request, flow)
            return (
                redirect(
                    reverse("shared_waiver", args=[share_token]) + "?signed=" + str(signature.pk)
                )
                if share
                else redirect("customer_waiver_complete")
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
            "progress_steps": progress(4, waivers=True) if flow else None,
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
        if flow.get("stage") not in {"waiver", "review", "details"}:
            raise ValidationError("Return to the current booking before signing.")
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


@enabled_view
@require_http_methods(["GET", "POST"])
def public_complete(request):
    if settings.RECOVERY_HOLD:
        return render(request, "core/booking_paused.html", status=503)
    try:
        flow = current(request)
        if flow.get("stage") == "done":
            return redirect("customer_booking_receipt")
        if flow.get("stage") not in {"waiver", "review"}:
            return redirect("customer_booking")
        signature = current_signatures(flow).filter(pk=flow.get("last_waiver_signature")).first()
        if signature is None:
            return redirect("customer_booking")
        form = CoverageConfirmationForm(
            request.POST if request.method == "POST" else None, flow=flow
        )
        if request.method == "POST":
            if (
                request.POST.get("wizard_key") != flow["key"]
                or request.POST.get("wizard_stage") != flow["stage"]
            ):
                return redirect("customer_booking")
            if form.is_valid():
                flow["waiver_share_requested"] = form.cleaned_data["coverage"] == "no"
                flow["waiver_coverage"] = not flow["waiver_share_requested"]
                flow["stage"] = "review"
                save(request, flow)
                return redirect("customer_booking")
        return render(
            request,
            "core/waivers/complete.html",
            {
                "flow": flow,
                "form": form,
                "signature": signature,
                "progress_steps": progress(4, waivers=True),
            },
        )
    except (ValidationError, ValueError):
        return redirect("customer_booking")


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
            exact, possible = name_candidates(query)
            direct = (
                Q(signer_name__icontains=query)
                | Q(signer_email__icontains=query)
                | Q(minors__icontains=query)
                | Q(customer_links__customer_id__in=exact)
                | Q(booking_links__booking__customer_id__in=exact)
                | Q(customer_links__customer__email__icontains=query)
                | Q(customer_links__customer__previous_email__icontains=query)
                | Q(booking_links__booking__customer__email__icontains=query)
                | Q(booking_links__booking__customer__previous_email__icontains=query)
            )
            digits = phone_search_digits(query)
            if digits:
                direct |= (
                    Q(signer_phone__contains=digits)
                    | Q(customer_links__customer__phone__contains=digits)
                    | Q(customer_links__customer__previous_phone__contains=digits)
                    | Q(booking_links__booking__customer__phone__contains=digits)
                    | Q(booking_links__booking__customer__previous_phone__contains=digits)
                )
            direct_ids = WaiverSignature.objects.filter(direct).values("pk")
            possible_ids = WaiverSignature.objects.filter(
                Q(customer_links__customer_id__in=possible)
                | Q(booking_links__booking__customer_id__in=possible)
            ).values("pk")
            records = (
                records.filter(Q(pk__in=direct_ids) | Q(pk__in=possible_ids))
                .annotate(
                    possible_name_match=Case(
                        When(pk__in=direct_ids, then=Value(False)),
                        default=Value(True),
                        output_field=BooleanField(),
                    )
                )
                .order_by("possible_name_match", "-signed_at", "-pk")
            )
        if data["customer"]:
            records = records.filter(
                Q(customer_links__customer_id=data["customer"])
                | Q(booking_links__booking__customer_id=data["customer"])
            )
        if data["status"] == "valid":
            records = records.filter(
                state="signed", version_id__in=COVERAGE_VERSIONS, valid_until__gt=timezone.now()
            )
        elif data["status"] == "expired":
            records = records.filter(valid_until__lte=timezone.now())
        elif data["status"] == "superseded":
            records = records.exclude(version_id__in=COVERAGE_VERSIONS)
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
            "coverage_versions": COVERAGE_VERSIONS,
        },
    )


@staff_permission("core.view_waiversignature")
@enabled_view
@require_http_methods(["GET", "POST"])
def waiver_detail(request, pk):
    staff_access(request)
    signature = get_object_or_404(WaiverSignature.objects.select_related("version"), pk=pk)
    error = None
    if request.method == "POST":
        if not request.user.is_superuser:
            raise PermissionDenied
        from .services import reconcile_evidence

        try:
            reconcile_evidence(actor=request.user, signature_id=pk)
            messages.success(
                request, "The stored evidence was verified and its signing record completed."
            )
            return redirect("waiver_detail", pk=pk)
        except (EvidenceUnavailable, ValidationError, WaiverSignature.DoesNotExist):
            error = "The existing evidence could not be verified. It was not marked signed."
    return render(
        request,
        "core/waivers/detail.html",
        {
            "signature": signature,
            "waiver_now": timezone.now(),
            "current_version": VERSION,
            "coverage_versions": COVERAGE_VERSIONS,
            "error": error,
        },
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
    if request.POST.get("open_now") == "1":
        return redirect("shared_waiver", token=token)
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


@staff_permission("core.change_booking")
@staff_permission("core.view_booking")
@staff_permission("core.view_waiversignature")
@enabled_view
@require_POST
def paper_review(request, booking_id):
    from .forms import NamedPaperWaiverForm
    from .paper import record

    booking = get_object_or_404(Booking, pk=booking_id)
    form = NamedPaperWaiverForm(request.POST)
    if form.is_valid():
        try:
            record(actor=request.user, booking_id=booking_id, **form.cleaned_data)
            messages.success(request, "Named paper-waiver record saved.")
            return redirect("booking_detail", pk=booking_id)
        except ValidationError as error:
            form.add_error(None, error)
    return render(request, "core/waivers/paper_form.html", {"form": form, "booking": booking})
