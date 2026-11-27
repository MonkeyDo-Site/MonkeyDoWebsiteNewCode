"""Staff card setup in a booking-bound browser flow, separate from public tabs."""

import uuid
from datetime import timedelta
from functools import wraps

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from core.booking_completion import enabled
from core.communications.content import booking_confirmation, session_subject
from core.communications.services import enqueue
from core.models import AuditEvent, Booking
from core.permissions import staff_permission
from core.public_booking import DETAILS, LIFETIME, assert_flow, profile_proof
from core.waivers.coverage_forms import WaiverChoiceField
from core.waivers.models import BookingWaiverReview, WaiverBookingLink, WaiverSignature
from core.waivers.services import create_share, valid_customer_signatures

from .setup import authorize_actor, bind_booking, selected_consent
from .setup_views import card_context, setup_card, setup_status


def guarded(view):
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not settings.BOOKING_COMPLETION_ENABLED:
            raise Http404
        for permission in ("core.view_customer", "core.change_booking"):
            if not request.user.has_perm(permission):
                raise PermissionDenied
        return view(request, *args, **kwargs)

    return inner


def session_key(pk):
    return "staff_booking_card:" + str(pk)


def save_flow(request, flow):
    request.session[session_key(flow["staff_booking"])] = flow


def reader(booking_id):
    def read(request):
        flow = request.session.get(session_key(booking_id))
        assert_flow(flow)
        if flow.get("staff_booking") != booking_id:
            raise ValidationError("Return to the current staff booking setup.")
        authorize_actor(flow, request.user)
        return flow

    return read


def new_flow(request, booking, action="setup"):
    key = str(uuid.uuid4())
    flow = {
        "key": key,
        "stage": "review",
        "workflow": "integrated_v1",
        "expires": (timezone.now() + timedelta(seconds=LIFETIME)).timestamp(),
        "phone": booking.customer.phone,
        "proof": profile_proof(booking.customer, key),
        "staff_actor": request.user.pk,
        "staff_action": action,
        "staff_booking": booking.pk,
        "staff_booking_version": booking.edit_version,
        "session_id": booking.session_id,
        "details": {name: getattr(booking, name) for name in DETAILS},
    }
    save_flow(request, flow)
    return flow


class StaffConfirmForm(forms.Form):
    wizard_key = forms.UUIDField(widget=forms.HiddenInput)
    payment_consent = forms.UUIDField(widget=forms.HiddenInput)
    covered = forms.BooleanField(
        required=False, label="All participants are covered by the current waivers selected below."
    )
    paper_signatures = forms.ModelMultipleChoiceField(
        queryset=__import__(
            "core.waivers.models", fromlist=["PaperWaiver"]
        ).PaperWaiver.objects.none(),
        required=False,
        label="Current paper waivers",
        widget=forms.CheckboxSelectMultiple,
    )
    signatures = WaiverChoiceField(
        required=False,
        queryset=WaiverSignature.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Existing current waivers",
    )
    waiver_type = forms.ChoiceField(
        choices=[("single", "Single Waiver"), ("multiple", "Multiple waivers")],
        label="Waiver instruction type",
    )
    confirm = forms.BooleanField(
        label="Confirm this sandbox booking. Payment will be collected only after staff arrival review."
    )

    def __init__(self, *args, booking, **kwargs):
        super().__init__(*args, **kwargs)
        from .checkout import charge_state

        if charge_state(booking).comped:
            self.fields["payment_consent"].required = False
        from core.waivers.paper import current_paper

        self.fields["paper_signatures"].queryset = current_paper(
            booking.customer, booking.session.starts_at
        )
        self.minimum_minors = booking.children + booking.babies
        self.fields["signatures"].queryset = valid_customer_signatures(
            booking.customer, at=booking.session.starts_at
        )

    def clean(self):
        data = super().clean()
        if data.get("covered"):
            selected = list(data.get("signatures") or []) + list(data.get("paper_signatures") or [])
            names = {
                name.casefold().strip() for signature in selected or [] for name in signature.minors
            }
            if not selected or len(names) < self.minimum_minors:
                raise forms.ValidationError(
                    "Select current waiver coverage for all participants, or leave coverage pending and send signing instructions."
                )
        return data


@transaction.atomic
def finalize(*, actor, booking_id, flow, values):
    enabled()
    authorize_actor(flow, actor)
    booking = (
        Booking.objects.select_for_update()
        .select_related("customer", "session")
        .get(pk=booking_id, workflow="integrated_v1")
    )
    from .checkout import charge_state

    comped = charge_state(booking).comped
    if str(values["wizard_key"]) != flow["key"] or (
        not comped and str(values["payment_consent"]) != flow.get("payment_consent")
    ):
        raise ValidationError(
            "Card setup changed. Review and save the chosen card before confirming."
        )
    if not booking.setup_pending:
        return booking
    if not comped:
        selected_consent(flow)
        if hasattr(booking, "card_agreement"):
            from .setup import replace_booking_card

            replacement = dict(flow, staff_action="replace")
            replace_booking_card(actor=actor, booking_id=booking.pk, flow=replacement)
        else:
            bind_booking(flow=flow, booking=booking)
    review, _ = BookingWaiverReview.objects.get_or_create(booking=booking)
    if values["covered"]:
        allowed = set(
            valid_customer_signatures(booking.customer, at=booking.session.starts_at).values_list(
                "pk", flat=True
            )
        )
        from core.waivers.paper import current_paper

        papers = list(values.get("paper_signatures") or [])
        allowed_paper = set(
            current_paper(booking.customer, booking.session.starts_at).values_list("pk", flat=True)
        )
        if (
            (not values["signatures"] and not papers)
            or any(item.pk not in allowed for item in values["signatures"])
            or any(item.pk not in allowed_paper for item in papers)
        ):
            raise ValidationError("Current participant coverage must be reviewed again.")
        for signature in values["signatures"]:
            WaiverBookingLink.objects.get_or_create(signature=signature, booking=booking)
        review.coverage_confirmed = True
        review.revision += 1
        review.save(update_fields=["coverage_confirmed", "revision", "updated_at"])
    from core.membership_booking import confirm as confirm_membership

    confirm_membership(booking, actor=actor)
    booking.setup_pending = False
    booking.save(update_fields=["setup_pending"])
    if booking.customer.email:
        waiver_url = None
        if not review.coverage_confirmed and not review.paper_signed:
            _, token = create_share(actor=actor, booking_id=booking.pk)
            waiver_url = settings.BOOKING_STAGING_ORIGIN + reverse("shared_waiver", args=[token])
        enqueue(
            key=f"booking-confirmation:{booking.pk}",
            kind="booking_waiver" if waiver_url else "booking_confirmation",
            recipient=booking.customer.email,
            subject=session_subject(booking),
            text=booking_confirmation(
                booking, waiver_url=waiver_url, waiver_type=values["waiver_type"], comped=comped
            ),
            customer=booking.customer,
            booking=booking,
            unsigned_waiver=bool(waiver_url and values["waiver_type"] == "multiple"),
            actor=actor,
        )
    AuditEvent.objects.create(
        actor=actor,
        action="booking.setup_completed",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "waiver_complete": review.coverage_confirmed,
            "confirmation_queued": bool(booking.customer.email),
        },
    )
    return booking


@staff_permission("core.view_booking")
@guarded
@require_http_methods(["GET", "POST"])
def staff_booking_setup(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related("customer", "session"), pk=pk, workflow="integrated_v1"
    )
    if not booking.setup_pending:
        return redirect("booking_detail", pk=pk)
    try:
        flow = reader(pk)(request)
    except ValidationError:
        flow = new_flow(request, booking)
    form = StaffConfirmForm(
        request.POST if request.method == "POST" else None,
        booking=booking,
        initial={
            "wizard_key": flow["key"],
            "payment_consent": flow.get("payment_consent"),
            "waiver_type": "single",
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            finalize(actor=request.user, booking_id=pk, flow=flow, values=form.cleaned_data)
            messages.success(request, "Sandbox booking confirmed. Admission has not been charged.")
            if not booking.customer.email:
                messages.warning(
                    request,
                    "No current customer email is recorded, so no confirmation email was queued.",
                )
            return redirect("booking_detail", pk=pk)
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
    from .checkout import charge_state

    context = card_context(flow) if not charge_state(booking).comped else {"comped": True}
    endpoint = reverse("staff_card_setup", args=[pk])
    context.update(
        card_endpoint=endpoint,
        card_status_url=endpoint + flow["payment_setup_key"] + "/"
        if flow.get("payment_setup_key")
        else "",
        card_staff=True,
    )
    return render(
        request,
        "core/staff_booking_setup.html",
        context | {"booking": booking, "flow": flow, "form": form},
    )


@staff_permission("core.view_booking")
@guarded
@require_POST
def staff_card_setup(request, pk):
    return setup_card(request, reader=reader(pk), writer=save_flow, actor=request.user)


@staff_permission("core.view_booking")
@guarded
@require_GET
def staff_card_status(request, pk, setup_id):
    return setup_status(request, setup_id, reader=reader(pk), writer=save_flow)


class ReplaceCardForm(forms.Form):
    wizard_key = forms.UUIDField(widget=forms.HiddenInput)
    payment_consent = forms.UUIDField(widget=forms.HiddenInput)
    confirm = forms.BooleanField(widget=forms.HiddenInput, initial=True)


@staff_permission("core.view_booking")
@guarded
@require_http_methods(["GET", "POST"])
def replace_card(request, pk):
    from .checkout import summary
    from .setup import replace_booking_card

    booking = get_object_or_404(
        Booking.objects.select_related("customer", "session"), pk=pk, workflow="integrated_v1"
    )
    if not hasattr(booking, "card_agreement"):
        return redirect("staff_booking_setup", pk=pk)
    if booking.attendance and not summary(booking).get("can_collect"):
        messages.info(
            request, "There is no unresolved reviewed balance requiring a replacement card."
        )
        return redirect("booking_detail", pk=pk)
    try:
        flow = reader(pk)(request)
        if flow.get("staff_action") != "replace":
            raise ValidationError("Open the replacement form.")
    except ValidationError:
        flow = new_flow(request, booking, action="replace")
    from . import arrival_drafts

    draft_token = request.GET.get("draft") or flow.get("arrival_draft")
    if draft_token:
        try:
            arrival_drafts.get(request, booking, draft_token)
        except ValidationError:
            raise Http404 from None
        flow["arrival_draft"] = draft_token
        save_flow(request, flow)
    return_url = (
        arrival_drafts.url(booking, draft_token)
        if draft_token
        else reverse("booking_detail", args=[pk])
    )
    form = ReplaceCardForm(
        request.POST if request.method == "POST" else None,
        initial={
            "wizard_key": flow["key"],
            "payment_consent": flow.get("payment_consent"),
            "confirm": True,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            if str(form.cleaned_data["wizard_key"]) != flow["key"] or str(
                form.cleaned_data["payment_consent"]
            ) != flow.get("payment_consent"):
                raise ValidationError("Card setup changed. Review the current replacement source.")
            replace_booking_card(actor=request.user, flow=flow, booking_id=pk)
            messages.success(request, "Booking card updated. No payment was charged.")
            return redirect(return_url)
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
    from .checkout import charge_state

    context = card_context(flow) if not charge_state(booking).comped else {"comped": True}
    endpoint = reverse("staff_card_setup", args=[pk])
    context.update(
        card_endpoint=endpoint,
        card_status_url=endpoint + flow["payment_setup_key"] + "/"
        if flow.get("payment_setup_key")
        else "",
        card_staff=True,
    )
    return render(
        request,
        "core/replace_booking_card.html",
        context
        | {
            "booking": booking,
            "flow": flow,
            "form": form,
            "card_replacement": True,
            "return_url": return_url,
        },
    )
