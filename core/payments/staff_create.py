"""One-page staff creation: private drafts; a booking exists only after confirmation."""

import copy
import uuid
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from core.booking_forms import TestBookingForm, session_capacity_summary, session_date_picker
from core.booking_management import create_test_booking
from core.models import AuditEvent, Booking, BookingCapacityHold, PricingPolicy
from core.permissions import require_actor, staff_permission
from core.public_booking import DETAILS, assert_flow, profile_proof
from core.waivers.forms import NamedPaperWaiverForm, SignatureForm
from core.waivers.paper import current_paper
from core.waivers.services import valid_customer_signatures

from .checkout_pricing import visit_lines
from .ledger import fingerprint, lock_request
from .models import PaymentSetup
from .setup import authorize_actor, flow_identity, selected_consent
from .setup_views import card_context, setup_card, setup_status
from .staff_setup import StaffConfirmForm, finalize

KEY = "staff_booking_create_drafts"


def permitted(actor):
    for permission in (
        "core.add_booking",
        "core.view_booking",
        "core.change_booking",
        "core.view_customer",
    ):
        require_actor(actor, permission)


def write(request, flow):
    values = {
        k: v
        for k, v in request.session.get(KEY, {}).items()
        if v.get("expires", 0) > timezone.now().timestamp()
    }
    values[flow["key"]] = flow
    request.session[KEY] = dict(list(values.items())[-12:])


def read(request, token):
    permitted(request.user)
    try:
        flow = request.session[KEY][str(uuid.UUID(str(token)))]
        assert_flow(flow)
    except (KeyError, ValueError, TypeError) as error:
        raise ValidationError("This booking draft expired. Open Add booking again.") from error
    if flow.get("staff_actor") != request.user.pk or flow.get("staff_action") != "create":
        raise PermissionDenied
    flow = copy.deepcopy(flow)
    if flow.get("customer_id"):
        from core.models import Customer

        customer = Customer.objects.filter(
            pk=flow["customer_id"], revision=flow.get("customer_revision"), phone=flow.get("phone")
        ).first()
        if customer:
            # Staff already chose this exact customer in this private draft.
            # Refresh only the proof; never the hold or draft expiration.
            flow["proof"] = profile_proof(customer, flow["key"])
    return flow


def new(request):
    permitted(request.user)
    flow = {
        "key": str(uuid.uuid4()),
        "expires": (timezone.now() + timedelta(hours=2)).timestamp(),
        "staff_actor": request.user.pk,
        "staff_action": "create",
        "workflow": "integrated_v1",
        "stage": "review",
        "fields": {},
    }
    write(request, flow)
    return flow


class OwnerPriceForm(forms.Form):
    price_mode = forms.ChoiceField(
        choices=[
            ("standard", "Standard pricing"),
            ("special", "Custom admissions price"),
            ("comped", "Complimentary — entire booking $0"),
        ],
        initial="standard",
        widget=forms.RadioSelect,
    )
    custom_admissions = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=14,
        decimal_places=2,
        label="Admissions total",
        help_text="Admissions only. Grip socks are charged separately.",
    )

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def clean(self):
        data = super().clean()
        if not self.owner and (
            data.get("price_mode") not in {None, "standard"}
            or data.get("custom_admissions") is not None
        ):
            raise PermissionDenied
        if data.get("price_mode") == "special" and data.get("custom_admissions") is None:
            self.add_error("custom_admissions", "Enter the agreed admissions total.")
        if data.get("price_mode") != "special":
            data["custom_admissions"] = None
        return data


class DraftPaperForm(NamedPaperWaiverForm):
    clean_minors = SignatureForm.clean_minors

    def clean(self):
        data = super().clean()
        if data.get("relationship") == "Legal guardian" and any(
            len(name.split()) < 2 for name in data.get("minors", [])
        ):
            self.add_error(
                "minors",
                "Enter a first and last name for every minor when signing as a legal guardian.",
            )
        if data.get("signed_on") and data["signed_on"] > timezone.localdate():
            self.add_error("signed_on", "Use the actual signing date, no later than today.")
        return data


class DraftWaivers(StaffConfirmForm):
    """One coverage answer; current records are determined by the server."""

    waiver_choice = forms.ChoiceField(
        label="Is everyone in this booking covered by these waivers?",
        choices=[
            ("covered", "Yes, everyone is covered."),
            ("link", "Include the waiver link in the confirmation email."),
        ],
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, customer, session, children, babies, pending_paper=None, **kwargs):
        forms.Form.__init__(self, *args, **kwargs)
        self.fields["payment_consent"].required = False
        self.fields["confirm"].widget = forms.HiddenInput()
        self.fields["confirm"].initial = True
        self.fields["signatures"].queryset = valid_customer_signatures(
            customer, at=session.starts_at
        )
        self.fields["paper_signatures"].queryset = current_paper(customer, session.starts_at)
        self.current_waivers = [
            *self.fields["signatures"].queryset,
            *self.fields["paper_signatures"].queryset,
        ]
        self.fields["waiver_type"].label = "Waiver-link instructions"
        self.fields["waiver_type"].choices = [
            ("single", "For this customer to sign"),
            ("multiple", "For this customer to share with other parents"),
        ]
        self.minimum_minors = children + babies
        self.pending_paper = pending_paper

    def clean(self):
        data = forms.Form.clean(self)
        data["covered"] = data.get("waiver_choice") == "covered"
        data["signatures"] = self.fields["signatures"].queryset
        data["paper_signatures"] = self.fields["paper_signatures"].queryset
        if data.get("covered"):
            selected = list(data.get("signatures") or []) + list(data.get("paper_signatures") or [])
            names = {name.strip().casefold() for signature in selected for name in signature.minors}
            if self.pending_paper:
                names.update(name.strip().casefold() for name in self.pending_paper["minors"])
            if (not selected and not self.pending_paper) or len(names) < self.minimum_minors:
                self.add_error(
                    "waiver_choice",
                    "The current waivers do not list enough minors for this booking. Sign or record the remaining waivers here, or choose to include the waiver link in the confirmation email.",
                )
        return data


def posted_fields(post):
    allowed = (
        set(TestBookingForm.base_fields)
        | set(OwnerPriceForm.base_fields)
        | set(DraftWaivers.base_fields)
        | {"paper-" + key for key in NamedPaperWaiverForm.base_fields}
    )
    return {
        key: post.getlist(key) if key in {"signatures", "paper_signatures"} else post.get(key, "")
        for key in allowed
        if key in post
    }


def quote_for(data, owner_price):
    from core.pricing import Line, quote_lines

    policy = PricingPolicy.objects.first()
    if not policy:
        raise ValidationError("Pricing is unavailable.")
    from core import membership_booking

    if membership_booking.active():
        return membership_booking.new_quote(
            policy,
            customer_id=data["customer"].pk,
            session=data["session"],
            values=data,
            special_admissions=owner_price["custom_admissions"],
            comped=owner_price["price_mode"] == "comped",
        )
    lines = visit_lines(
        policy,
        **{k: data[k] for k in DETAILS if k != "expected_method"},
        special_admissions=owner_price["custom_admissions"],
    )
    comped = owner_price["price_mode"] == "comped"
    if comped:
        lines = [Line(row.label, row.quantity, Decimal("0"), row.taxable) for row in lines]
    quote = quote_lines(
        lines,
        policy,
        card_base=None if data["expected_method"] == "card" and not comped else Decimal("0"),
    )
    quote.update(
        expected_method=data["expected_method"],
        owner_comped=comped,
        owner_special_admissions=str(owner_price["custom_admissions"])
        if owner_price["custom_admissions"] is not None
        else None,
    )
    return quote


def review(request, flow, post, *, final=False):
    if len(post.urlencode().encode()) > 40000:
        raise ValidationError("The booking form is too large.")
    booking_form = TestBookingForm(post, owner=request.user.is_superuser, previewing=not final)
    price_form = OwnerPriceForm(post, owner=request.user.is_superuser)
    paper_form = DraftPaperForm(
        post if post.get("paper-paper_signed") else None,
        prefix="paper",
        initial={"request_key": flow.get("paper_key") or uuid.uuid4()},
    )
    valid = booking_form.is_valid() & price_form.is_valid()
    if str(booking_form.cleaned_data.get("creation_key", "")) != flow["key"]:
        booking_form.add_error(None, "Open the current booking draft again.")
        valid = False
    flow["fields"] = posted_fields(post)
    write(request, flow)
    if not valid:
        return booking_form, price_form, paper_form, None, None
    data = booking_form.cleaned_data
    session = data["session"]
    quote = quote_for(data, price_form.cleaned_data)
    customer = data["customer"]
    identity_changed = flow.get("customer_id") not in {None, customer.pk} or flow.get(
        "customer_revision"
    ) not in {None, customer.revision}
    if identity_changed:
        if PaymentSetup.objects.filter(
            flow_hash=flow_identity(flow)[0],
            state__in=["unknown", "customer_sending", "method_sending"],
        ).exists():
            raise ValidationError("Resolve the existing card setup before changing customers.")
        for key in (
            "payment_setup_key",
            "payment_consent",
            "waiver_signatures",
            "last_waiver_signature",
        ):
            flow.pop(key, None)
    from core.booking_holds import reserve

    reserve(
        key=flow["key"],
        actor=request.user,
        customer=customer,
        session=session,
        **{key: data[key] for key in ("children", "adults", "babies", "supervised")},
        override=data.get("override_capacity", False),
        renew=final or post.get("intent") == "renew",
    )
    old_policy = flow.get("quote", {}).get("policy_id")
    if flow.get("details", {}).get("expected_method", data["expected_method"]) != data[
        "expected_method"
    ] or (old_policy is not None and old_policy != quote["policy_id"]):
        flow.pop("payment_consent", None)
        flow["payment_method_changed"] = True
    flow.update(
        customer_id=customer.pk,
        customer_revision=customer.revision,
        phone=customer.phone,
        proof=profile_proof(customer, flow["key"]),
        session_id=session.pk,
        details={k: data[k] for k in DETAILS},
        quote=quote,
    )
    write(request, flow)
    pending = None
    if post.get("paper-paper_signed") and final:
        if paper_form.is_valid():
            pending = paper_form.cleaned_data
        else:
            return booking_form, price_form, paper_form, None, quote
    initial = {
        k: post.getlist(k) if k in {"signatures", "paper_signatures"} else post.get(k, "")
        for k in DraftWaivers.base_fields
    }
    initial.update(
        wizard_key=flow["key"], confirm=True, waiver_type=post.get("waiver_type") or "single"
    )
    if identity_changed:
        initial.update(waiver_choice="", covered=False, signatures=[], paper_signatures=[])
    waivers = DraftWaivers(
        post if final else None,
        customer=customer,
        session=session,
        children=data["children"],
        babies=data["babies"],
        pending_paper=pending,
        initial=initial,
    )
    if final and not waivers.is_valid():
        return booking_form, price_form, paper_form, waivers, None
    return booking_form, price_form, paper_form, waivers, quote


def digest(data, price, quote):
    return fingerprint(
        {
            "customer": data["customer"].pk,
            "customer_revision": data["customer"].revision,
            "session": data["session"].pk,
            "counts": {k: data[k] for k in DETAILS},
            "owner": {k: str(v) if v is not None else None for k, v in price.items()},
            "quote": quote,
            "override": data.get("override_capacity", False),
            "close": data.get("close_session", False),
            "sender": data.get("zelle_sender", ""),
        }
    )


def context_card(flow):
    context = card_context(flow, empty=not bool(flow.get("proof")))
    endpoint = reverse("staff_create_card", args=[flow["key"]])
    context.update(
        card_staff=True,
        card_staff_create=True,
        card_endpoint=endpoint,
        card_status_url=endpoint + flow["payment_setup_key"] + "/"
        if flow.get("payment_setup_key")
        else "",
    )
    return context


def membership_context(flow):
    from core.membership_booking import active, summaries
    from core.models import Session

    session = Session.objects.filter(pk=flow.get("session_id")).first() if active() else None
    return {
        "session": session,
        "membership_rows": summaries(flow.get("customer_id"), session, flow.get("quote")),
    }


def response_context(request, flow, forms_tuple):
    from core.booking_holds import describe

    booking_form, price_form, paper_form, waivers, quote = forms_tuple
    context = context_card(flow)
    current_signatures = (
        list(waivers.fields["signatures"].queryset)
        + list(waivers.fields["paper_signatures"].queryset)
        if waivers
        else []
    )
    return {
        "valid": quote is not None
        and not any(form.errors for form in forms_tuple[:4] if form is not None),
        "html": render_to_string("core/quote_items.html", {"data": quote}, request=request)
        if quote
        else "",
        "membership_html": render_to_string(
            "core/partials/booking_memberships.html", membership_context(flow), request=request
        ),
        "waivers_html": render_to_string(
            "core/partials/staff_create_waivers.html", {"waiver_form": waivers}, request=request
        )
        if waivers
        else "",
        "waiver_revision": fingerprint(
            {
                "customer": flow.get("customer_id"),
                "session": flow.get("session_id"),
                "waivers": [str(x.pk) for x in current_signatures],
            }
        ),
        "comped": quote.get("owner_comped", False) if quote else False,
        "customer_id": flow.get("customer_id"),
        "hold": describe(flow["key"], request.user),
        "capacity": session_capacity_summary(booking_form.cleaned_data["session"])
        if booking_form.cleaned_data.get("session")
        else "",
        "methods": [
            {"id": str(method.pk), "last_four": method.last_four}
            for method in context["card_methods"]
        ],
        "ready": context["card_ready"],
        "consent": context["card_accepted_consent"],
        "selected_method": str(context["card_accepted_method_id"] or ""),
        "status_url": context["card_status_url"],
        "request_key": str(context["card_setup_key"]),
        "cancellation": context["card_cancellation_policy"],
        "errors": {
            key: form.errors.get_json_data()
            for key, form in [
                ("booking", booking_form),
                ("price", price_form),
                ("waivers", waivers),
                ("paper", paper_form),
            ]
            if form is not None and form.errors
        },
    }


@transaction.atomic
def commit_booking(request, flow, post, result):
    booking_form, price_form, paper_form, waivers, quote = result
    if quote is None or not waivers or not waivers.is_valid():
        raise ValidationError("Review the booking and waiver details before confirming.")
    current = digest(booking_form.cleaned_data, price_form.cleaned_data, quote)
    if post.get("reviewed_hash") != current:
        raise ValidationError(
            "The booking price changed. Review the current estimate before confirming."
        )
    from core.calendar import lock_calendar

    lock_calendar(exclusive=booking_form.cleaned_data.get("close_session", False))
    key = lock_request(flow["key"])
    existing = Booking.objects.filter(creation_key=key).first()
    if existing:
        event = AuditEvent.objects.filter(
            action="booking.single_page_confirmed",
            record_type="booking",
            record_id=str(existing.reference),
        ).first()
        if (
            not event
            or event.changes.get("fingerprint") != current
            or existing.creation_actor_id != request.user.pk
        ):
            raise ValidationError("This booking request was already used. Open the saved booking.")
        return existing
    comped = price_form.cleaned_data["price_mode"] == "comped"
    if not comped:
        accepted = selected_consent(flow)
        if str(accepted.pk) != post.get("payment_consent"):
            raise ValidationError("Review the selected booking card again.")
    hold = (
        BookingCapacityHold.objects.select_for_update().filter(pk=key, actor=request.user).first()
    )
    if not hold or hold.expires_at <= timezone.now():
        raise ValidationError(
            "The temporary reservation expired. Reserve the places again before confirming."
        )
    # Remove the temporary count in the same transaction that creates the
    # permanent reservation. Failure rolls the hold deletion back as well.
    hold.delete()
    values = dict(booking_form.cleaned_data)
    values.pop("session_date", None)
    values.pop("estimate_token", None)
    values.pop("version", None)
    values.pop("special_admissions", None)
    values["session_id"] = values.pop("session").pk
    values["workflow"] = "integrated_v1"
    booking = create_test_booking(actor=request.user, **values)
    if price_form.cleaned_data["price_mode"] != "standard":
        from .comped import set_price

        booking = set_price(
            actor=request.user,
            booking_id=booking.pk,
            version=booking.edit_version,
            comped=comped,
            special_admissions=price_form.cleaned_data["custom_admissions"],
        )
    saved_quote = booking.quotes.first().snapshot
    if any(
        saved_quote.get(key) != quote.get(key)
        for key in (
            "policy_id",
            "lines",
            "subtotal",
            "processing_fee",
            "sales_tax",
            "total",
            "membership_plan",
        )
    ):
        raise ValidationError(
            "Pricing changed while confirming. Review the new estimate and confirm again."
        )
    final_post = post.copy()
    final_post["covered"] = "on" if waivers.cleaned_data["covered"] else ""
    final_post.setlist("signatures", [str(item.pk) for item in waivers.cleaned_data["signatures"]])
    final_post.setlist(
        "paper_signatures", [str(item.pk) for item in waivers.cleaned_data["paper_signatures"]]
    )
    if post.get("paper-paper_signed"):
        from core.waivers.paper import record

        if not paper_form.is_valid():
            raise ValidationError("Review the signed paper waiver details.")
        item = record(actor=request.user, booking_id=booking.pk, **paper_form.cleaned_data)
        final_post.setlist(
            "paper_signatures", final_post.getlist("paper_signatures") + [str(item.pk)]
        )
    final_flow = dict(
        flow,
        staff_action="setup",
        staff_booking=booking.pk,
        staff_booking_version=booking.edit_version,
    )
    confirm = StaffConfirmForm(final_post, booking=booking)
    if not confirm.is_valid():
        raise ValidationError(
            [str(error) for errors in confirm.errors.values() for error in errors]
        )
    finalize(
        actor=request.user, booking_id=booking.pk, flow=final_flow, values=confirm.cleaned_data
    )
    review_record = booking.waiver_review
    review_record.share_requested = waivers.cleaned_data["waiver_choice"] == "link"
    review_record.save(update_fields=["share_requested", "updated_at"])
    AuditEvent.objects.create(
        actor=request.user,
        action="booking.single_page_confirmed",
        record_type="booking",
        record_id=str(booking.reference),
        changes={
            "fingerprint": current,
            "waiver_choice": waivers.cleaned_data["waiver_choice"],
            "waiver_link_requested": review_record.share_requested,
        },
    )
    return booking


@sensitive_post_parameters()
def page(request):
    try:
        return page_content(request)
    except ValidationError as error:
        if request.method == "POST":
            return JsonResponse({"valid": False, "error": " ".join(error.messages)}, status=400)
        messages.warning(request, " ".join(error.messages))
        return redirect("booking_create")


def page_content(request):
    permitted(request.user)
    flow = (
        read(request, request.POST.get("draft") or request.GET["draft"])
        if request.POST.get("draft") or request.GET.get("draft")
        else new(request)
    )
    if request.method == "GET" and request.GET.get("hold_status"):
        from core.booking_holds import describe
        from core.models import Session

        session = Session.objects.filter(pk=flow.get("session_id")).first()
        return JsonResponse(
            {
                "hold": describe(flow["key"], request.user),
                "capacity": session_capacity_summary(session) if session else "",
            }
        )
    if flow.get("completed_booking"):
        if request.method == "POST":
            return JsonResponse(
                {
                    "confirmed": True,
                    "valid": True,
                    "url": reverse("booking_detail", args=[flow["completed_booking"]]),
                }
            )
        return redirect("booking_detail", pk=flow["completed_booking"])
    if request.method == "POST":
        try:
            intent = request.POST.get("intent", "confirm")
            if intent == "confirm":
                existing = Booking.objects.filter(
                    creation_key=flow["key"], creation_actor=request.user
                ).first()
                if (
                    existing
                    and AuditEvent.objects.filter(
                        action="booking.single_page_confirmed",
                        record_type="booking",
                        record_id=str(existing.reference),
                        changes__fingerprint=request.POST.get("reviewed_hash"),
                    ).exists()
                ):
                    flow["completed_booking"] = existing.pk
                    write(request, flow)
                    return JsonResponse(
                        {
                            "valid": True,
                            "confirmed": True,
                            "url": reverse("booking_detail", args=[existing.pk]),
                        }
                    )
            result = review(request, flow, request.POST, final=intent in {"prepare", "confirm"})
            answer = response_context(request, flow, result)
            if intent in {"prepare", "confirm"} and answer["valid"]:
                answer["reviewed_hash"] = digest(
                    result[0].cleaned_data, result[1].cleaned_data, result[4]
                )
                if intent == "confirm":
                    booking = commit_booking(request, flow, request.POST, result)
                    flow["completed_booking"] = booking.pk
                    write(request, flow)
                    answer.update(confirmed=True, url=reverse("booking_detail", args=[booking.pk]))
            return JsonResponse(answer, status=200 if answer["valid"] else 400)
        except ValidationError as error:
            from core.booking_holds import describe

            return JsonResponse(
                {
                    "valid": False,
                    "error": " ".join(error.messages),
                    "hold": describe(flow["key"], request.user),
                },
                status=400,
            )
    initial = flow.get("fields", {}) | {"creation_key": flow["key"]}
    for key in ("customer", "session"):
        if not request.GET.get("draft") and request.GET.get(key, "").isdigit():
            initial[key] = request.GET[key]
    booking_form = TestBookingForm(owner=request.user.is_superuser)
    booking_form.initial.update(initial)
    session_date_picker(booking_form)
    for name in ("expected_method", "zelle_sender"):
        if name in booking_form.fields:
            booking_form.fields[name].widget.attrs["form"] = "customer-booking-form"
    if initial.get("customer"):
        from core.booking_forms import customer_picker

        customer_picker(booking_form)
    price_form = OwnerPriceForm(
        owner=request.user.is_superuser, initial={"price_mode": "standard"} | initial
    )
    flow.setdefault("paper_key", str(uuid.uuid4()))
    write(request, flow)
    paper_initial = {
        key.removeprefix("paper-"): value
        for key, value in initial.items()
        if key.startswith("paper-")
    }
    paper_form = DraftPaperForm(
        prefix="paper", initial={"request_key": flow["paper_key"]} | paper_initial
    )
    waiver_form = None
    if str(initial.get("customer", "")) == str(flow.get("customer_id", "")) and flow.get(
        "customer_id"
    ):
        from core.models import Customer, Session

        customer = Customer.objects.filter(pk=flow["customer_id"]).first()
        session = Session.objects.filter(pk=flow.get("session_id")).first()
        if customer and session:
            waiver_form = DraftWaivers(
                customer=customer,
                session=session,
                children=flow["details"]["children"],
                babies=flow["details"]["babies"],
                initial={"waiver_type": "single"} | initial,
            )
    return render(
        request,
        "core/staff_booking_create.html",
        context_card(flow)
        | membership_context(flow)
        | {
            "flow": flow,
            "form": booking_form,
            "price_form": price_form,
            "paper_form": paper_form,
            "waiver_form": waiver_form,
            "paper_checked": bool(initial.get("paper-paper_signed")),
        },
    )


@staff_permission("core.add_booking")
@require_POST
def card(request, token):
    return setup_card(
        request, reader=lambda req: ready(req, token), writer=write, actor=request.user
    )


def ready(request, token):
    flow = read(request, token)
    authorize_actor(flow, request.user)
    return flow


@staff_permission("core.add_booking")
@require_GET
def card_status(request, token, setup_id):
    return setup_status(request, setup_id, reader=lambda req: ready(req, token), writer=write)


@staff_permission("core.add_booking")
@staff_permission("core.view_waiversignature")
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters()
def sign_waiver(request, token):
    from core.waivers.services import approved_version, sign
    from core.waivers.storage import EvidenceUnavailable

    try:
        flow = ready(request, token)
        version = approved_version()
    except ValidationError as error:
        return JsonResponse({"error": " ".join(error.messages)}, status=400)
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
            signature = sign(
                data=request.POST,
                flow=flow,
                ip=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            AuditEvent.objects.create(
                actor=request.user,
                action="waiver.staff_draft_signed",
                record_type="customer",
                record_id=str(flow["customer_id"]),
                changes={"signature_id": str(signature.pk)},
            )
            return JsonResponse({"signed": True, "signature_id": str(signature.pk)})
        except (ValidationError, EvidenceUnavailable) as error:
            form.add_error(
                None,
                " ".join(error.messages)
                if isinstance(error, ValidationError)
                else "We could not confirm that the waiver was saved. Keep this page open and try again.",
            )
    return JsonResponse(
        {
            "html": render_to_string(
                "core/partials/staff_create_sign.html",
                {"form": form, "legal_html": version.legal_html},
                request=request,
            )
        },
        status=400 if form.errors else 200,
    )
