import uuid
from datetime import timedelta
from functools import wraps

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from .account_security import allow_security_request
from .forms import normalize_phone
from .models import Booking, Customer
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
        return view(request, *args, **kwargs)

    return wrapped


def save(request, flow):
    request.session[SESSION_KEY] = flow


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
        label="Phone number (you may also try a previous number)",
        widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
    )

    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"])


class NameForm(forms.Form):
    last_name = forms.CharField(max_length=120, label="Last Name")


class SimilarNameForm(forms.Form):
    confirm_similar_name = forms.BooleanField(
        label="I confirm that I entered my own family’s phone number and last name."
    )


class ContactForm(forms.Form):
    last_name = forms.CharField(max_length=120, label="Last Name")
    email = forms.EmailField(label="Email address")


class PreviousPhoneForm(forms.Form):
    confirm_phone = forms.ChoiceField(
        choices=[("yes", "Yes"), ("no", "No")],
        widget=forms.RadioSelect,
        label="Is this your current phone number?",
    )


class DetailsForm(forms.Form):
    play_type = forms.ChoiceField(widget=forms.RadioSelect, choices=[])
    children = forms.IntegerField(
        min_value=0,
        max_value=35,
        initial=1,
        label="Children (ages 1–11 for Open Play; 3–11 for Supervised Play)",
    )
    adults = forms.IntegerField(min_value=0, max_value=50, initial=1, label="Adults ages 12+")
    babies = forms.IntegerField(min_value=0, max_value=50, initial=0, label="Babies under one")
    socks = forms.IntegerField(min_value=0, max_value=35, initial=0, label="Pairs of grip socks")
    expected_method = forms.ChoiceField(
        choices=Booking._meta.get_field("expected_method").choices, label="Payment method"
    )
    referral_source = forms.CharField(
        max_length=240, required=False, label="How did you hear about MonkeyDo?"
    )

    def __init__(self, *args, session, **kwargs):
        super().__init__(*args, **kwargs)
        choices = []
        if session.play_mode != "supervised":
            choices.append(("open", "Open Play"))
        if (
            session.play_mode != "accompanied"
            and timezone.now() < session.starts_at
            and session.supervised_capacity
        ):
            choices.append(("supervised", "Supervised Play"))
        self.fields["play_type"].choices = choices
        self.fields["play_type"].initial = choices[0][0] if choices else None

    def clean(self):
        from .pricing import validate_attendees

        data = super().clean()
        if self.errors:
            return data
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


def display(request, flow, *, form=None, error=None):
    session = public_session(flow["session_id"])
    customer = customer_from_flow(flow) if flow.get("proof") else None
    return render(
        request,
        "core/customer_booking.html",
        {
            "flow": flow,
            "session": session,
            "form": form,
            "error": error,
            "customer": customer,
            "quote": flow.get("quote"),
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
    save(request, flow)
    return redirect("customer_booking")


@enabled
@sensitive_post_parameters("phone", "last_name", "email")
@require_http_methods(["GET", "POST"])
def wizard(request):
    try:
        flow = current(request)
        if flow["stage"] == "done":
            return redirect("customer_booking_receipt")
        session = public_session(flow["session_id"])
        stage = flow["stage"]
        form_type = {
            "phone": PhoneForm,
            "name": NameForm,
            "name_confirm": SimilarNameForm,
            "previous": PreviousPhoneForm,
            "contact": ContactForm,
            "details": DetailsForm,
            "review": ConfirmForm,
        }.get(stage)
        if form_type is None:
            raise ValidationError("Start a new booking session.")
        args = {"session": session} if stage == "details" else {}
        if stage == "details" and flow.get("details"):
            args["initial"] = flow["details"] | {
                "play_type": "supervised" if flow["details"]["supervised"] else "open"
            }
        form = form_type(request.POST if request.method == "POST" else None, **args)
        if stage == "review" and request.method == "GET":
            form = ConfirmForm(initial={"flow_key": flow["key"]})
        if request.method == "POST" and form.is_valid():
            limit(request, stage, 60)
            data = form.cleaned_data
            if stage == "phone":
                if not allow_security_request("public-booking-phone:" + data["phone"], 8):
                    raise ValidationError(
                        "Please call or text 848-238-5147 for help with this booking."
                    )
                customer = lookup_phone(data["phone"])
                flow["phone"] = data["phone"]
                flow["visited"] = data["visited"]
                flow["stage"] = "contact"
                if customer:
                    flow["candidate"] = {"id": customer.pk, "revision": customer.revision}
                    flow["stage"] = "name" if customer.phone == data["phone"] else "previous"
                    if flow["stage"] == "previous":
                        flow["current_phone"] = customer.phone
            elif stage in {"name", "name_confirm", "previous"}:
                candidate = flow["candidate"]
                customer = Customer.objects.get(pk=candidate["id"])
                if customer.revision != candidate["revision"]:
                    raise ValidationError("Customer details changed. Please start again.")
                if stage == "name":
                    exact = canonical_name(data["last_name"]) == canonical_name(customer.last_name)
                    if not exact and similar_name(data["last_name"], customer.last_name):
                        flow["entered_name"] = data["last_name"]
                        flow["stage"] = "name_confirm"
                        save(request, flow)
                        return redirect("customer_booking")
                    matched = exact
                elif stage == "name_confirm":
                    matched = data["confirm_similar_name"] and similar_name(
                        flow.get("entered_name", ""), customer.last_name
                    )
                else:
                    matched = data["confirm_phone"] == "yes"
                if not matched:
                    flow["stage"] = "blocked"
                    save(request, flow)
                    message = (
                        "The last name you entered doesn't match the name on record for this number. We would love to get your booking done for you as soon as possible. Please call or text 848-238-5147 and we'll help you with it."
                        if stage in {"name", "name_confirm"}
                        else "We would love to get your booking finalized as soon as possible. Please call/text 848-238-5147 for assistance with this booking."
                    )
                    return render(
                        request, "core/customer_booking.html", {"error": message}, status=400
                    )
                flow["proof"] = profile_proof(customer, flow["key"])
                flow["verification_mode"] = stage
                flow["stage"] = "details"
            elif stage == "contact":
                flow["contact"] = {"last_name": data["last_name"].strip(), "email": data["email"]}
                flow["stage"] = "details"
            elif stage == "details":
                flow["quote"] = review_quote(flow, data)
                flow["details"] = data
                flow["stage"] = "review"
            elif stage == "review":
                if str(data["flow_key"]) != flow["key"]:
                    raise ValidationError(
                        "Another booking was started in this browser. Please review it again."
                    )
                try:
                    booking = submit_booking(flow)
                except ValidationError:
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
        {"booking": booking, "quote": booking.quotes.first()},
    )


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
