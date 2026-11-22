import uuid
from datetime import timedelta
from functools import wraps

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from . import public_verification
from .account_security import allow_security_request
from .booking_progress import progress
from .forms import normalize_phone, payment_method_choices
from .models import Booking, Customer, PricingPolicy, SiteSettings
from .name_matching import similar_name
from .public_booking import (
    LIFETIME,
    assert_flow,
    canonical_name,
    customer_from_flow,
    lookup_phone,
    profile_proof,
    public_session,
    review_quote,
    submit_booking,
)

SESSION_KEY = "customer_test_booking"


def enabled(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not settings.CUSTOMER_TEST_BOOKING or settings.DESIGN_REVIEW_ONLY:
            raise Http404
        if settings.RECOVERY_HOLD:
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
    return flow


def limit(request, action, count=30):
    if not allow_security_request(
        f"public-booking:{action}:{request.META.get('REMOTE_ADDR', 'unknown')}", count
    ):
        raise ValidationError("Please wait before trying again, or call/text 848-238-5147.")


class PhoneForm(forms.Form):
    visited = forms.ChoiceField(
        choices=[("no", "No"), ("yes", "Yes")],
        widget=forms.RadioSelect,
        label="Have you visited MonkeyDo before?",
    )
    phone = forms.CharField(
        max_length=40,
        label="Enter your phone number",
        widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
    )

    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"])


class NameForm(forms.Form):
    last_name = forms.CharField(max_length=120, label="Last Name")


class SimilarNameForm(forms.Form):
    pass  # The explicit Continue action confirms the phone-selected spelling match.


class RetryPhoneForm(forms.Form):
    phone = forms.CharField(
        max_length=40,
        required=False,
        label="Try another phone number",
        widget=forms.TextInput(attrs={"type": "tel"}),
    )

    def clean_phone(self):
        if self.data.get("continue_new") == "1":
            return ""
        return normalize_phone(self.cleaned_data["phone"], optional=True)


class EmailRecoveryForm(forms.Form):
    email = forms.EmailField(label="Email address")


def recovery_match_kind(flow, customer):
    """Match current email plus earlier inputs; never request a surname twice."""
    phone_customer = lookup_phone(flow["phone"])
    if phone_customer is not None:
        return "phone_email" if phone_customer.pk == customer.pk else None
    entered_name = flow.get("entered_name", "")
    return "name_email" if entered_name and similar_name(entered_name, customer.last_name) else None


class ContactForm(forms.Form):
    last_name = forms.CharField(max_length=120, label="Last Name")
    email = forms.EmailField(label="Email address")
    referral_source = forms.CharField(
        max_length=240, required=False, label="How did you hear about MonkeyDo?"
    )

    def clean_email(self):
        from .customers import check_email_available

        email = self.cleaned_data["email"].strip().lower()
        try:
            check_email_available(email)
        except ValidationError:
            from .customers import public_duplicate_email_message

            raise ValidationError(
                public_duplicate_email_message(email), code="duplicate_email"
            ) from None
        return email


class RequiredEmailForm(forms.Form):
    email = forms.EmailField(label="Email address")

    def clean_email(self):
        from .customers import check_email_available

        email = self.cleaned_data["email"].strip().lower()
        try:
            check_email_available(email)
        except ValidationError:
            from .customers import public_duplicate_email_message

            raise ValidationError(
                public_duplicate_email_message(email), code="duplicate_email"
            ) from None
        return email


class PreviousPhoneForm(forms.Form):
    confirm_phone = forms.ChoiceField(
        choices=[("yes", "Yes"), ("no", "No")],
        widget=forms.RadioSelect,
        label="Is this your current phone number?",
    )


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
        self.fields[
            "socks"
        ].help_text = "Grip socks are required for play at MonkeyDo. You can pay for them now or bring your own. Select the number of pairs you want to purchase."
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


def display(request, flow, *, form=None, error=None, notice=None):
    session = public_session(flow["session_id"])
    customer = customer_from_flow(flow) if flow.get("proof") else None
    completing = flow.get("workflow") == "integrated_v1"
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
        form_type = {
            "phone": PhoneForm,
            "retry_phone": RetryPhoneForm,
            "name": public_verification.NameOrEmailForm
            if flow.get("verification_entry") == "returning_current"
            else NameForm,
            "name_confirm": SimilarNameForm,
            "email_lookup": EmailRecoveryForm,
            "email_confirm": SimilarNameForm,
            "previous": PreviousPhoneForm,
            "contact": ContactForm,
            "email": RequiredEmailForm,
            "details": DetailsForm,
            "review": confirm_type,
            "waiver": CoverageForm if completing else None,
            **public_verification.FORMS,
        }.get(stage)
        if form_type is None:
            raise ValidationError("Start a new booking session.")
        args = {"session": session} if stage == "details" else {}
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
            if public_verification.handle(flow, form, stage):
                save(request, flow)
                if form.errors:
                    return display(request, flow, form=form)
                return redirect("customer_booking")
            if stage == "phone":
                # Re-entering identity always re-verifies it; never retain an old
                # profile proof or contact while processing another phone.
                for field in (
                    "proof",
                    "candidate",
                    "candidate_name",
                    "contact",
                    "contact_email",
                    "payment_consent",
                    "waiver_coverage",
                    "waiver_share_requested",
                ):
                    flow.pop(field, None)
                if not allow_security_request("public-booking-phone:" + data["phone"], 8):
                    raise ValidationError(
                        "Please call or text 848-238-5147 for help with this booking."
                    )
                customer = lookup_phone(data["phone"])
                flow["phone"] = data["phone"]
                flow["visited"] = data["visited"]
                flow["stage"] = "contact"
                flow["contact_origin"] = "new"
                flow["lookup_note"] = not bool(customer)
                if not customer and data["visited"] == "yes":
                    flow["stage"] = "retry_phone"
                if customer:
                    flow["candidate"] = {"id": customer.pk, "revision": customer.revision}
                    flow["stage"] = "name" if customer.phone == data["phone"] else "previous"
                    if flow["stage"] == "name":
                        flow["verification_entry"] = "returning_current"
                    if flow["stage"] == "previous":
                        flow["current_phone"] = customer.phone
            elif stage == "retry_phone":
                phone = data.get("phone")
                if request.POST.get("continue_new") == "1":
                    flow["stage"] = "contact"
                    flow["contact_origin"] = "explicit_new"
                elif not phone:
                    form.add_error(
                        "phone", "Enter another phone number, or choose Continue as a new customer."
                    )
                    return display(request, flow, form=form)
                else:
                    if not allow_security_request("public-booking-phone:" + phone, 8):
                        raise ValidationError(
                            "Please call/text 848-238-5147 for help with this booking."
                        )
                    customer = lookup_phone(phone)
                    flow["phone"] = phone
                    if customer:
                        flow["candidate"] = {"id": customer.pk, "revision": customer.revision}
                        flow["stage"] = "name" if customer.phone == phone else "previous"
                        if flow["stage"] == "name":
                            flow["verification_entry"] = "returning_current"
                        if flow["stage"] == "previous":
                            flow["current_phone"] = customer.phone
                    else:
                        flow["stage"] = "contact"
                        flow["contact_origin"] = "retry_unmatched"
                        flow["lookup_note"] = True
            elif stage == "email_lookup":
                address = data["email"].strip().lower()
                if not allow_security_request("public-booking-email:" + address, 8):
                    raise ValidationError(
                        "Please wait before trying again, or call/text 848-238-5147."
                    )
                customer = Customer.objects.filter(email__iexact=address).first()
                matched_by = recovery_match_kind(flow, customer) if customer is not None else None
                if not matched_by:
                    # Only the unmatched-phone failure from comment 8 loses its
                    # introduction. Other legacy recovery contexts retain theirs.
                    if lookup_phone(flow["phone"]) is None:
                        flow["unmatched_email_failed"] = True
                        save(request, flow)
                    form.add_error(
                        None,
                        "We couldn't match those details. Please try again or call/text 848-238-5147 for help.",
                    )
                    return display(request, flow, form=form)
                flow["candidate"] = {"id": customer.pk, "revision": customer.revision}
                flow["candidate_name"] = customer.last_name
                flow["recovery_match_kind"] = matched_by
                flow["recovery_email"] = address
                flow["stage"] = "email_confirm"
            elif stage in {"name", "name_confirm", "previous", "email_confirm"}:
                candidate = flow["candidate"]
                customer = Customer.objects.get(pk=candidate["id"])
                if customer.revision != candidate["revision"]:
                    raise ValidationError("Customer details changed. Please start again.")
                if stage == "name":
                    flow["entered_name"] = data["last_name"]
                    exact = canonical_name(data["last_name"]) == canonical_name(customer.last_name)
                    if not exact and similar_name(data["last_name"], customer.last_name):
                        flow["entered_name"] = data["last_name"]
                        flow["candidate_name"] = customer.last_name
                        flow["stage"] = "name_confirm"
                        save(request, flow)
                        return redirect("customer_booking")
                    matched = exact
                elif stage == "email_confirm":
                    matched = customer.email.casefold() == flow.get(
                        "recovery_email", ""
                    ).casefold() and bool(recovery_match_kind(flow, customer))
                elif stage == "name_confirm":
                    matched = similar_name(flow.get("entered_name", ""), customer.last_name)
                else:
                    matched = data["confirm_phone"] == "yes"
                if not matched and stage in {"name", "name_confirm"}:
                    flow["stage"] = "email_lookup"
                    flow.pop("candidate_name", None)
                    save(request, flow)
                    recovery = EmailRecoveryForm()
                    flow["recovery_notice"] = (
                        "We couldn't match that name to the entered phone number."
                    )
                    save(request, flow)
                    return display(request, flow, form=recovery)
                if not matched:
                    flow["stage"] = "blocked"
                    save(request, flow)
                    message = (
                        f"The last name you entered doesn't match the name on record for number {flow['phone']}. We would love to get your booking completed as soon as possible. Please call or text 848-238-5147 and we'll be happy to help you with it."
                        if stage in {"name", "name_confirm"}
                        else "We would love to get your booking finalized as soon as possible. Please call/text 848-238-5147 for assistance with this booking."
                    )
                    return render(
                        request, "core/customer_booking.html", {"error": message}, status=400
                    )
                flow.pop("lookup_note", None)
                flow.pop("contact", None)
                flow["proof"] = profile_proof(customer, flow["key"])
                flow["verification_mode"] = stage
                flow["stage"] = "details" if customer.email else "email"
            elif stage == "email":
                flow["contact_email"] = data["email"]
                flow["stage"] = "details"
            elif stage == "contact":
                flow.pop("lookup_note", None)
                flow["new_contact_ready"] = True
                flow["contact"] = {
                    "last_name": data["last_name"].strip(),
                    "email": data["email"],
                    "referral_source": data["referral_source"],
                }
                flow["stage"] = "details"
            elif stage == "details":
                if (
                    flow.get("details", {}).get("expected_method", data["expected_method"])
                    != data["expected_method"]
                ):
                    flow.pop("payment_consent", None)
                    flow["payment_method_changed"] = True
                flow["quote"] = review_quote(flow, data)
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


@enabled
@require_http_methods(["GET"])
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
    return render(
        request,
        "core/customer_booking_receipt.html",
        {
            "booking": booking,
            "quote": booking.quotes.first(),
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
        return JsonResponse(
            {
                "html": render_to_string(
                    "core/partials/live_quote.html", {"data": quote}, request=request
                )
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
