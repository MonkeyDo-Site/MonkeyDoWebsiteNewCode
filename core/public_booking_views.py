import uuid
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from . import public_identity, public_verification
from .account_security import allow_security_request
from .booking_progress import progress
from .forms import payment_method_choices
from .models import Booking, Customer, PricingPolicy, SiteSettings
from .public_booking import (
    LIFETIME,
    assert_flow,
    customer_from_flow,
    public_session,
    review_quote,
    submit_booking,
)
from .public_identity import ContactForm, RequiredEmailForm

SESSION_KEY = "customer_test_booking"


def enabled(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not settings.CUSTOMER_TEST_BOOKING or settings.DESIGN_REVIEW_ONLY:
            raise Http404
        if settings.RECOVERY_HOLD or (
            settings.APP_ENV == "staging"
            and not settings.BOOKING_COMPLETION_ENABLED
            and view.__name__ in {"start", "wizard"}
        ):
            return render(request, "core/booking_paused.html", status=503)
        response = view(request, *args, **kwargs)
        add_never_cache_headers(response)
        return response

    return wrapped


def save(request, flow):
    from .booking_navigation import remember

    request.session[SESSION_KEY] = flow
    remember(request, flow)


def current(request):
    flow = request.session.get(SESSION_KEY)
    assert_flow(flow)
    if (
        settings.BOOKING_COMPLETION_ENABLED
        and flow.get("workflow") != "integrated_v1"
        and flow.get("stage") != "done"
    ):
        # A stale pre-integration browser flow must not create a new legacy reservation.
        flow["workflow"] = "integrated_v1"
        flow["stage"] = (
            "details" if flow.get("details") else "contact" if flow.get("contact") else "phone"
        )
        flow.pop("quote", None)
        flow["navigation_revision"] = flow.get("navigation_revision", 0) + 1
        save(request, flow)
    return flow


def limit(request, action, count=30):
    if not allow_security_request(
        f"public-booking:{action}:{request.META.get('REMOTE_ADDR', 'unknown')}", count
    ):
        raise ValidationError("Please wait before trying again, or call/text 848-238-5147.")


class AvailablePlayRadio(forms.RadioSelect):
    def __init__(self, available):
        self.available = available
        super().__init__()

    def create_option(self, name, value, label, selected, index, **kwargs):
        option = super().create_option(name, value, label, selected, index, **kwargs)
        if not self.available.get(value, False):
            option["attrs"]["disabled"] = True
        return option


class DetailsForm(forms.Form):
    play_type = forms.ChoiceField(widget=forms.RadioSelect, choices=[])
    children = forms.IntegerField(
        min_value=0,
        max_value=35,
        initial=1,
        label="Number of children",
        help_text="Ages 1–11 for Open Play | Ages 3–11 for Supervised Play.",
    )
    adults = forms.IntegerField(
        min_value=0, max_value=50, initial=1, label="Number of adults", help_text="Ages 12 and up."
    )
    babies = forms.IntegerField(
        min_value=0, max_value=50, initial=0, label="Number of babies", help_text="Under age one."
    )
    socks = forms.IntegerField(min_value=0, max_value=35, initial=0, label="Grip socks")
    expected_method = forms.ChoiceField(
        choices=Booking._meta.get_field("expected_method").choices, label="Payment method"
    )

    zelle_sender = forms.CharField(
        required=False, max_length=160, label="Zelle sender name/account"
    )

    def __init__(self, *args, session, require_sender=True, **kwargs):
        self.require_sender = require_sender
        super().__init__(*args, **kwargs)
        if not settings.BOOKING_COMPLETION_ENABLED:
            self.fields.pop("zelle_sender")
        from .availability import availability

        horizon = (
            SiteSettings.objects.filter(pk=1).values_list("booking_horizon_days", flat=True).first()
            or 1
        )
        state = availability(session, horizon)
        self.available_play = {
            "open": bool(state.get("accompanied_available")),
            "supervised": bool(state.get("supervised_available")),
        }
        self.fields["play_type"].widget = AvailablePlayRadio(self.available_play)
        self.fields["play_type"].choices = [
            (
                value,
                label
                if self.available_play[value]
                else label + " (not available for this session)",
            )
            for value, label in (("open", "Open Play"), ("supervised", "Supervised Play"))
        ]
        self.fields["play_type"].initial = "open" if self.available_play["open"] else "supervised"
        self.supervised_available = self.available_play["supervised"]
        if not self.available_play["open"] and self.supervised_available:
            self.fields["adults"].initial = self.fields["babies"].initial = 0
        policy = PricingPolicy.objects.first()
        sock_price = policy.sock_price if policy else "1.99"
        self.fields["socks"].help_text = (
            "Grip socks are required for play at MonkeyDo. You can pay for them now or bring your own. "
            f"Select the number of pairs you want to purchase. Grip socks are ${sock_price} a pair."
        )
        self.fields["adults"].widget.attrs["min"] = 1 if self.available_play["open"] else 0
        self.fields["expected_method"].choices = payment_method_choices(
            PricingPolicy.objects.first()
        )

    def clean(self):
        from .pricing import validate_attendees

        data = super().clean()
        if self.errors:
            return data
        if not self.available_play.get(data["play_type"]):
            self.add_error("play_type", "This play type is not available for this session.")
            return data
        if "zelle_sender" in self.fields:
            from .payments.receipts import sender

            data["zelle_sender"] = (
                sender(
                    data.get("zelle_sender", ""),
                    required=self.require_sender and data["expected_method"] == "zelle",
                )
                if data["expected_method"] == "zelle"
                else ""
            )
        data["supervised"] = data.pop("play_type") == "supervised"
        if not data["supervised"] and data["adults"] < 1:
            self.add_error(
                "adults", "An adult must accompany a baby or child to an open play session."
            )
            return data
        validate_attendees(
            **{k: data[k] for k in ("children", "adults", "babies", "socks", "supervised")}
        )
        return data


class ConfirmForm(forms.Form):
    flow_key = forms.UUIDField(widget=forms.HiddenInput)
    acknowledge_test = forms.BooleanField(
        label="I understand this is a pending test reservation, not a confirmed visit. No card will be charged."
    )


class CompletedConfirmForm(ConfirmForm):
    payment_consent = forms.UUIDField(widget=forms.HiddenInput)
    acknowledge_test = forms.BooleanField(
        label="I understand this is a sandbox booking. Admission payment is collected only after staff review at arrival."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if settings.APP_ENV == "production":
            self.fields.pop("acknowledge_test", None)


def display(request, flow, *, form=None, error=None, notice=None):
    session = public_session(flow["session_id"])
    customer = customer_from_flow(flow) if flow.get("proof") else None
    completing = flow.get("workflow") == "integrated_v1"
    from .membership_booking import summaries
    from .membership_booking_prompts import context as prompt_context

    membership_rows = (
        summaries(customer.pk if customer else None, session, flow.get("quote"))
        if completing
        else []
    )
    card = {}
    if completing and flow["stage"] == "review":
        from .payments.setup import selected_consent
        from .payments.setup_views import card_context

        card = card_context(flow)
        try:
            card["accepted_card"] = selected_consent(flow).method
        except ValidationError:
            pass
    return render(
        request,
        "core/customer_booking.html",
        {
            "progress_steps": progress(
                3
                if flow["stage"] == "details"
                else 4
                if flow["stage"] == "waiver"
                else (5 if completing else 4)
                if flow["stage"] == "review"
                else 2,
                waivers=completing,
            ),
            "flow": flow,
            "membership_rows": membership_rows,
            **(
                prompt_context(
                    customer=customer,
                    flow=flow,
                    source="public",
                    pending_email=flow.get("contact_email", ""),
                )
                if completing and flow["stage"] == "details"
                else {}
            ),
            "renewal_form_url": reverse("public_membership_choice"),
            "booking_history_page": True,
            "waiver_choices": form if flow["stage"] == "waiver" else None,
            **card,
            "session": session,
            "form": form,
            "error": error,
            "flow_notice": notice,
            "show_contact_recovery": flow["stage"] == "contact"
            and flow.get("contact_origin") == "retry_unmatched"
            and not (form and form.errors),
            **public_verification.choice_context(flow),
            "customer": customer,
            "quote": flow.get("quote"),
            "live_quote": initial_live_quote(form, flow) if flow["stage"] == "details" else None,
        },
    )


@enabled
@require_POST
def start(request, session_id):
    try:
        limit(request, "start")
        public_session(session_id)
    except ValidationError as exc:
        return render(
            request, "core/customer_booking.html", {"error": " ".join(exc.messages)}, status=400
        )
    request.session.cycle_key()
    flow = {
        "key": str(uuid.uuid4()),
        "session_id": session_id,
        "expires": (timezone.now() + timedelta(seconds=LIFETIME)).timestamp(),
        "stage": "phone",
    }
    if settings.BOOKING_COMPLETION_ENABLED:
        from .booking_completion import enabled as completion_enabled

        completion_enabled()
        flow["workflow"] = "integrated_v1"
    save(request, flow)
    return redirect("customer_booking")


@enabled
@sensitive_post_parameters("phone", "last_name", "email")
@require_http_methods(["GET", "POST"])
def wizard(request):
    try:
        flow = current(request)
        if (
            request.method == "GET"
            and request.GET.get("restart") == "1"
            and flow["stage"] != "done"
        ):
            flow = {
                key: flow[key]
                for key in ("key", "session_id", "expires", "workflow")
                if key in flow
            }
            flow["stage"] = "phone"
            save(request, flow)
            return redirect("customer_booking")
        if flow["stage"] == "done":
            return redirect("customer_booking_receipt")
        from .booking_navigation import restore

        flow, navigation_response = restore(request, flow)
        if navigation_response is not None:
            return navigation_response
        save(request, flow)
        session = public_session(flow["session_id"])
        stage = flow["stage"]
        completing = flow.get("workflow") == "integrated_v1"
        from .waivers.coverage_forms import CoverageForm

        confirm_type = CompletedConfirmForm if completing else ConfirmForm
        form_type = public_identity.form_type(flow) or {
            "details": DetailsForm,
            "review": confirm_type,
            "waiver": CoverageForm if completing else None,
        }.get(stage)
        if form_type is None:
            raise ValidationError("Start a new booking session.")
        args = {"session": session} if stage == "details" else {}
        if stage in {"contact", "email"}:
            args["phone"] = flow["phone"]
        if flow.get("answers", {}).get(stage):
            args["initial"] = flow["answers"][stage]
        if stage == "waiver":
            args["flow"] = flow
        if stage == "details" and flow.get("details"):
            args["initial"] = flow["details"] | {
                "play_type": "supervised" if flow["details"]["supervised"] else "open"
            }
        form = form_type(request.POST if request.method == "POST" else None, **args)
        if (
            request.method == "POST"
            and "wizard_key" in request.POST
            and (
                request.POST.get("wizard_key") != flow["key"]
                or request.POST.get("wizard_stage") != stage
            )
        ):
            fresh_args = dict(args)
            if stage == "review":
                fresh_args["initial"] = {"flow_key": flow["key"]}
                if completing:
                    fresh_args["initial"]["payment_consent"] = flow.get("payment_consent")
            return display(
                request,
                flow,
                form=form_type(**fresh_args),
                notice="Your booking changed in another tab or an earlier step. Please review this page before continuing.",
            )
        if stage == "review" and request.method == "GET":
            form = confirm_type(
                initial={"flow_key": flow["key"], "payment_consent": flow.get("payment_consent")}
            )
        if request.method == "POST" and stage == "contact":
            form.is_valid()
            if form.cleaned_data.get("last_name"):
                flow["entered_name"] = form.cleaned_data["last_name"]
                save(request, flow)
        if request.method == "POST" and form.is_valid():
            limit(request, stage, 60)
            data = form.cleaned_data
            from .booking_navigation import remember_answers

            remember_answers(flow, stage, form, request.POST)
            save(request, flow)
            identity_step = public_identity.advance(flow, form, post=request.POST)
            if identity_step is not None:
                save(request, flow)
                if identity_step.error:
                    return render(
                        request,
                        "core/customer_booking.html",
                        {"error": identity_step.error},
                        status=400,
                    )
                if identity_step.display:
                    return display(request, flow, form=identity_step.form)
                return redirect("customer_booking")
            if stage == "details":
                if (
                    flow.get("details", {}).get("expected_method", data["expected_method"])
                    != data["expected_method"]
                ):
                    flow.pop("payment_consent", None)
                    flow["payment_method_changed"] = True
                try:
                    flow["quote"] = review_quote(flow, data)
                except ValidationError as exc:
                    if getattr(exc, "code", None) != "session_capacity":
                        raise
                    # Preserve this attempt for the explicit return-to-amounts action.
                    # It remains at details and must pass a fresh quote before continuing.
                    flow["details"] = data
                    flow.pop("quote", None)
                    save(request, flow)
                    return render(
                        request,
                        "core/customer_booking.html",
                        {
                            "error": " ".join(exc.messages),
                            "capacity_recovery": True,
                            "flow": flow,
                            "session": session,
                            "progress_steps": progress(3, waivers=completing),
                        },
                        status=400,
                    )
                flow["details"] = data
                flow["stage"] = "waiver" if completing else "review"
            elif stage == "waiver":
                if data.get("sign_now"):
                    flow["waiver_share_requested"] = data.get("share_requested") is True
                    flow["waiver_signatures"] = list(
                        dict.fromkeys(
                            flow.get("waiver_signatures", [])
                            + [str(item.pk) for item in data["signatures"]]
                        )
                    )
                    save(request, flow)
                    return redirect("customer_waiver")
                flow["waiver_signatures"] = [str(item.pk) for item in data["signatures"]]
                flow["waiver_share_requested"] = data.get("share_requested") is True
                flow["waiver_coverage"] = (
                    not flow["waiver_share_requested"] and data.get("coverage_confirmed") is True
                )
                flow["stage"] = "review"
            elif stage == "review":
                if completing and str(data["payment_consent"]) != flow.get("payment_consent"):
                    form.add_error(
                        None,
                        "Card setup changed. Please review and save your chosen card before confirming.",
                    )
                    return display(request, flow, form=form)
                if str(data["flow_key"]) != flow["key"]:
                    raise ValidationError(
                        "Another booking was started in this browser. Please review it again."
                    )
                try:
                    booking = submit_booking(flow)
                except ValidationError as exc:
                    if hasattr(exc, "message_dict") and "email" in exc.message_dict:
                        flow["stage"] = "email" if flow.get("proof") else "contact"
                        save(request, flow)
                        retry = (
                            RequiredEmailForm({"email": flow.get("contact_email", "")})
                            if flow.get("proof")
                            else ContactForm(flow.get("contact"))
                        )
                        retry.is_valid()
                        if "email" not in retry.errors:
                            retry.add_error("email", exc.message_dict["email"])
                        return display(request, flow, form=retry)
                    # A policy/capacity/contact change never silently finalizes an old estimate.
                    flow["stage"] = "details"
                    flow.pop("quote", None)
                    save(request, flow)
                    raise
                flow["stage"] = "done"
                flow["booking_id"] = booking.pk
                save(request, flow)
                return redirect("customer_booking_receipt")
            save(request, flow)
            return redirect("customer_booking")
        return display(request, flow, form=form)
    except (ValidationError, Customer.DoesNotExist) as exc:
        message = (
            " ".join(exc.messages)
            if isinstance(exc, ValidationError)
            else "Customer details changed. Please start again."
        )
        return render(request, "core/customer_booking.html", {"error": message}, status=400)


class AvailableBenefitForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    reviewed_hash = forms.CharField(max_length=64, widget=forms.HiddenInput)
    confirmed = forms.BooleanField(label="Confirm the updated booking price")


@enabled
@require_http_methods(["GET", "POST"])
def receipt(request):
    try:
        flow = current(request)
    except ValidationError:
        raise Http404 from None
    if flow.get("stage") != "done":
        raise Http404
    booking = (
        Booking.objects.select_related("customer", "session")
        .filter(pk=flow.get("booking_id"), creation_key=flow["key"], source="customer_test")
        .first()
    )
    if not booking:
        raise Http404
    from .communications.content import zelle_instructions

    benefit, benefit_form, benefit_error = None, None, ""
    if settings.MEMBERSHIP_SALES_ENABLED and booking.workflow == "integrated_v1":
        from . import membership_public_benefits

        if request.method == "POST":
            posted = AvailableBenefitForm(request.POST)
            if posted.is_valid():
                try:
                    limit(request, "available-membership-benefit", 15)
                    membership_public_benefits.confirm(flow=flow, **posted.cleaned_data)
                    return redirect(reverse("customer_booking_receipt") + "?benefit=updated")
                except ValidationError as error:
                    benefit_error = " ".join(error.messages)
            else:
                benefit_error = "Review the updated price and confirm it using the button below."
        try:
            benefit = membership_public_benefits.review(flow=flow)
        except ValidationError:
            pass
        if benefit:
            benefit_form = AvailableBenefitForm(
                initial={"request_key": uuid.uuid4(), "reviewed_hash": benefit["fingerprint"]}
            )
    elif request.method == "POST":
        raise Http404
    quote = booking.quotes.first()
    from .payments.zelle import facts as zelle_facts
    from .price_adjustments import booking_price_adjustment

    prepaid = zelle_facts(booking) if booking.workflow == "integrated_v1" else None

    return render(
        request,
        "core/customer_booking_receipt.html",
        {
            "booking": booking,
            "available_benefit": benefit,
            "benefit_form": benefit_form,
            "benefit_error": benefit_error,
            "receipt_prepayment": prepaid if not booking.attendance else None,
            "receipt_quote_label": "Booking price estimate"
            if prepaid and prepaid["received"] and not booking.attendance
            else "",
            "benefit_updated": bool(
                request.GET.get("benefit") == "updated"
                and quote
                and quote.snapshot.get("public_membership_benefit")
            ),
            "zelle_instructions": zelle_instructions()
            if booking.workflow == "integrated_v1"
            and booking.expected_method == "zelle"
            and not booking.attendance
            and quote is not None
            and not quote.snapshot.get("owner_comped")
            and (not prepaid or prepaid["available"] < Decimal(quote.snapshot["total"]))
            else "",
            "quote": quote,
            "receipt_adjustment": booking_price_adjustment(booking, quote.snapshot)
            if quote and booking.workflow == "integrated_v1"
            else None,
            "progress_steps": progress(
                5 if booking.workflow == "integrated_v1" else 4,
                done=True,
                waivers=booking.workflow == "integrated_v1",
            ),
            "progress_done": True,
            "booking_message": booking.messages.filter(
                kind__in=["booking_confirmation", "booking_waiver"]
            )
            .order_by("-created_at")
            .first()
            if booking.workflow == "integrated_v1"
            else None,
        },
    )


class PaymentMethodForm(forms.Form):
    expected_method = forms.ChoiceField(label="Payment method", choices=[])
    zelle_sender = forms.CharField(
        required=False, max_length=160, label="Zelle sender name/account"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expected_method"].choices = payment_method_choices(
            PricingPolicy.objects.first()
        )

    def clean(self):
        from .payments.receipts import sender

        data = super().clean()
        if data.get("expected_method") == "zelle":
            data["zelle_sender"] = sender(data.get("zelle_sender", ""), required=True)
        return data


@enabled
@require_http_methods(["GET", "POST"])
def payment_method(request):
    try:
        flow = current(request)
        if flow.get("stage") != "review" or flow.get("workflow") != "integrated_v1":
            return redirect("customer_booking")
        form = PaymentMethodForm(
            request.POST if request.method == "POST" else None, initial=flow["details"]
        )
        if request.method == "POST":
            if (
                request.POST.get("wizard_key") != flow["key"]
                or request.POST.get("wizard_stage") != flow["stage"]
            ):
                return redirect("customer_booking")
            if form.is_valid():
                from .payments.models import PaymentSetup
                from .payments.setup import flow_identity

                if PaymentSetup.objects.filter(
                    flow_hash=flow_identity(flow)[0],
                    state__in=["prepared", "customer_sending", "method_sending", "unknown"],
                ).exists():
                    form.add_error(
                        None, "Check the pending card setup before changing payment methods."
                    )
                    return render(request, "core/payment_method.html", {"flow": flow, "form": form})
                changed = flow["details"]["expected_method"] != form.cleaned_data["expected_method"]
                details = flow["details"] | form.cleaned_data
                if details["expected_method"] != "zelle":
                    details["zelle_sender"] = ""
                flow["quote"] = review_quote(flow, details)
                flow["details"] = details
                if changed:
                    flow.pop("payment_consent", None)
                    # Keep recovery of an unfinished exchange, but do not silently
                    # reuse its policy consent under another intended tender.
                    flow["payment_method_changed"] = True
                save(request, flow)
                return redirect("customer_booking")
        return render(
            request,
            "core/payment_method.html",
            {"flow": flow, "form": form, "progress_steps": progress(5, waivers=True)},
        )
    except ValidationError:
        return redirect("customer_booking")


@enabled
@require_POST
def revise(request):
    try:
        flow = current(request)
        if flow.get("stage") != "review" or request.POST.get("flow_key") != flow["key"]:
            raise ValidationError("Review the current booking before changing it.")
        flow["stage"] = "details"
        flow.pop("quote", None)
        save(request, flow)
    except ValidationError as exc:
        return render(
            request, "core/customer_booking.html", {"error": " ".join(exc.messages)}, status=400
        )
    return redirect("customer_booking")


@enabled
@require_http_methods(["GET", "POST"])
def recover_by_email(request):
    try:
        flow = current(request)
        if flow["stage"] not in {"contact", "retry_phone", "name", "email_lookup"}:
            raise ValidationError("Return to customer details to find your profile.")
        limit(request, "email-recovery", 12)
        flow["stage"] = "email_lookup"
        for key in ("candidate", "candidate_name", "proof", "contact", "lookup_note"):
            flow.pop(key, None)
        save(request, flow)
        return redirect("customer_booking")
    except ValidationError as exc:
        return render(
            request, "core/customer_booking.html", {"error": " ".join(exc.messages)}, status=400
        )


def initial_live_quote(form, flow):
    if form is None:
        return None
    values = {name: form[name].value() for name in form.fields}
    values["play_type"] = values.get("play_type") or form.fields["play_type"].initial
    values["expected_method"] = (
        values.get("expected_method") or form.fields["expected_method"].choices[0][0]
    )
    candidate = DetailsForm(
        values, session=public_session(flow["session_id"]), require_sender=False
    )
    if candidate.is_valid():
        try:
            quote = review_quote(flow, candidate.cleaned_data)
        except ValidationError:
            return None
        return quote
    return None


@enabled
@sensitive_post_parameters("phone", "last_name", "email")
@require_POST
def live_estimate(request):

    from django.http import JsonResponse
    from django.template.loader import render_to_string

    try:
        flow = current(request)
        if flow["stage"] != "details":
            raise ValidationError("Return to Session Details to update the estimate.")
        limit(request, "estimate", 240)
        form = DetailsForm(
            request.POST, session=public_session(flow["session_id"]), require_sender=False
        )
        if not form.is_valid():
            return JsonResponse(
                {
                    "error": "Enter valid quantities and an available play type to update the estimate."
                },
                status=400,
            )
        quote = review_quote(flow, form.cleaned_data)
        from .membership_booking import summaries
        from .membership_booking_prompts import context as prompt_context

        customer = customer_from_flow(flow) if flow.get("proof") else None
        membership = {
            **prompt_context(
                customer=customer,
                flow=flow,
                source="public",
                pending_email=flow.get("contact_email", ""),
            ),
            "membership_rows": summaries(
                customer.pk if customer else None, public_session(flow["session_id"]), quote
            ),
            "session": public_session(flow["session_id"]),
        }
        return JsonResponse(
            {
                "membership_html": render_to_string(
                    "core/partials/booking_memberships.html", membership, request=request
                ),
                "html": render_to_string(
                    "core/partials/live_quote.html", {"data": quote}, request=request
                ),
            },
            headers={"Cache-Control": "private, no-store"},
        )
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)


class CompletionEmailForm(forms.Form):
    email = forms.EmailField(label="Email address")
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    request_key = forms.UUIDField(widget=forms.HiddenInput)


@enabled
@sensitive_post_parameters("email")
@require_http_methods(["GET", "POST"])
def completion_email(request):
    from django.db import IntegrityError

    from .booking_email import correct_email

    try:
        flow = current(request)
    except ValidationError:
        raise Http404 from None
    if flow.get("stage") != "done" or flow.get("workflow") != "integrated_v1":
        raise Http404
    booking = (
        Booking.objects.select_related("customer")
        .filter(
            pk=flow.get("booking_id"),
            creation_key=flow["key"],
            source="customer_test",
            workflow="integrated_v1",
        )
        .first()
    )
    if not booking:
        raise Http404
    form = CompletionEmailForm(
        request.POST if request.method == "POST" else None,
        initial={
            "email": booking.customer.email,
            "version": booking.customer.revision,
            "request_key": uuid.uuid4(),
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            limit(request, "completion-email", 10)
            correct_email(flow=flow, **form.cleaned_data)
            return redirect("customer_booking_receipt")
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        except IntegrityError:
            form.add_error(
                "email",
                "That email address is already in use. Please enter a different address or call/text 848-238-5147.",
            )
    return render(request, "core/customer_booking_email.html", {"form": form})
