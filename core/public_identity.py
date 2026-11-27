"""Shared public customer matching, independent of visit or membership checkout.

The caller owns its browser flow, expiry, CSRF and request limit. Matching changes
only that flow; it does not create a customer, booking, capacity hold or payment.
"""

from dataclasses import dataclass

from django import forms
from django.core.exceptions import ValidationError

from . import public_verification
from .account_security import allow_security_request
from .forms import normalize_phone
from .models import Customer
from .name_matching import similar_name
from .public_booking import canonical_name, lookup_phone, profile_proof


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
    show_required_contact = True

    last_name = forms.CharField(max_length=120, label="Last Name")
    email = forms.EmailField(label="Email address")
    referral_source = forms.CharField(
        max_length=240, required=False, label="How did you hear about MonkeyDo?"
    )

    def __init__(self, *args, phone=None, **kwargs):
        self.phone = phone
        super().__init__(*args, **kwargs)

    def clean_email(self):
        from .customers import check_email_available

        email = self.cleaned_data["email"].strip().lower()
        try:
            check_email_available(email)
        except ValidationError:
            from .customers import public_duplicate_email_message

            raise ValidationError(
                public_duplicate_email_message(email, self.phone), code="duplicate_email"
            ) from None
        return email


class RequiredEmailForm(forms.Form):
    email = forms.EmailField(label="Email address")

    def __init__(self, *args, phone=None, **kwargs):
        self.phone = phone
        super().__init__(*args, **kwargs)

    def clean_email(self):
        from .customers import check_email_available

        email = self.cleaned_data["email"].strip().lower()
        try:
            check_email_available(email)
        except ValidationError:
            from .customers import public_duplicate_email_message

            raise ValidationError(
                public_duplicate_email_message(email, self.phone), code="duplicate_email"
            ) from None
        return email


class PreviousPhoneForm(forms.Form):
    confirm_phone = forms.ChoiceField(
        choices=[("yes", "Yes"), ("no", "No")],
        widget=forms.RadioSelect,
        label="Is this your current phone number?",
    )


def form_type(flow):
    return {
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
        **public_verification.FORMS,
    }.get(flow["stage"])


@dataclass(frozen=True)
class IdentityStep:
    form: forms.Form
    display: bool = False
    error: str = ""


def advance(flow, form, *, post):
    """Advance a valid identity form, or return None for a checkout-owned step."""
    stage = flow["stage"]
    if form_type(flow) is None:
        return None
    if not form.is_valid():
        raise ValueError("Validate the identity form before advancing it.")
    if public_verification.handle(flow, form, stage):
        return IdentityStep(form, display=bool(form.errors))
    data = form.cleaned_data
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
            raise ValidationError("Please call or text 848-238-5147 for help with this booking.")
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
        if post.get("continue_new") == "1":
            flow["stage"] = "contact"
            flow["contact_origin"] = "explicit_new"
        elif not phone:
            form.add_error(
                "phone", "Enter another phone number, or choose Continue as a new customer."
            )
            return IdentityStep(form, display=True)
        else:
            if not allow_security_request("public-booking-phone:" + phone, 8):
                raise ValidationError("Please call/text 848-238-5147 for help with this booking.")
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
            raise ValidationError("Please wait before trying again, or call/text 848-238-5147.")
        customer = Customer.objects.filter(email__iexact=address).first()
        matched_by = recovery_match_kind(flow, customer) if customer is not None else None
        if not matched_by:
            # Only the unmatched-phone failure from comment 8 loses its
            # introduction. Other legacy recovery contexts retain theirs.
            if lookup_phone(flow["phone"]) is None:
                flow["unmatched_email_failed"] = True
            form.add_error(
                None,
                "We couldn't match those details. Please try again or call/text 848-238-5147 for help.",
            )
            return IdentityStep(form, display=True)
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
                return IdentityStep(form)
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
            recovery = EmailRecoveryForm()
            flow["recovery_notice"] = "We couldn't match that name to the entered phone number."
            return IdentityStep(recovery, display=True)
        if not matched:
            flow["stage"] = "blocked"
            message = (
                f"The last name you entered doesn't match the name on record for number {flow['phone']}. We would love to get your booking completed as soon as possible. Please call or text 848-238-5147 and we'll be happy to help you with it."
                if stage in {"name", "name_confirm"}
                else "We would love to get your booking finalized as soon as possible. Please call/text 848-238-5147 for assistance with this booking."
            )
            return IdentityStep(form, error=message)
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
    return IdentityStep(form)
