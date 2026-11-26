"""Fourth-batch verification paths. No customer contact mutation or broad public search."""

import hashlib

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from .account_security import allow_security_request
from .customers import contact_lock
from .models import AuditEvent, Customer, OwnerNotice
from .name_matching import similar_name
from .public_booking import canonical_name, customer_from_flow, lookup_phone, profile_proof

ASSISTANCE = "848-238-5147"


class NameOrEmailForm(forms.Form):
    last_name = forms.CharField(max_length=120, required=False, label="Last Name")
    email = forms.EmailField(required=False, label="Email address")

    def clean(self):
        data = super().clean()
        if not self.errors and not (data.get("last_name") or data.get("email")):
            raise forms.ValidationError("Enter your last name or email address.")
        return data


class RecoveryNameForm(forms.Form):
    last_name = forms.CharField(max_length=120, label="Name")


class ProfileChoiceForm(forms.Form):
    email = forms.EmailField(required=False, label="Email address")
    last_name = forms.CharField(max_length=120, required=False, label="Last Name")


FORMS = {
    "recovered_name": RecoveryNameForm,
    "recovered_confirm": forms.Form,
    "name_retry": RecoveryNameForm,
    "conflict_name": RecoveryNameForm,
    "profile_choice": ProfileChoiceForm,
    "conflict_stop": forms.Form,
}


def recovered_customer(flow):
    saved = flow["recovered_candidate"]
    customer = Customer.objects.filter(pk=saved["id"], revision=saved["revision"]).first()
    if customer is None or customer.email.casefold() != flow["recovery_email"].casefold():
        raise ValidationError("Customer details changed. Please start again.")
    return customer


def prepare_recovered(flow, customer, address):
    for key in (
        "proof",
        "contact",
        "payment_consent",
        "waiver_signatures",
        "last_waiver_signature",
        "waiver_coverage",
    ):
        flow.pop(key, None)
    flow.update(
        recovered_candidate={"id": customer.pk, "revision": customer.revision},
        recovery_email=address,
        stage="recovered_confirm"
        if name_match(flow.get("entered_name", ""), customer)
        else "recovered_name",
    )


def name_match(entered, customer):
    if not entered:
        return ""
    if canonical_name(entered) == canonical_name(customer.last_name):
        return "exact"
    return "possible" if similar_name(entered, customer.last_name) else ""


def find_email(address):
    if not address:
        return None
    if not allow_security_request("public-booking-email:" + address, 8):
        raise ValidationError(f"Please wait before trying again, or call/text {ASSISTANCE}.")
    return Customer.objects.filter(email__iexact=address).first()


def original_customer(flow):
    customer = lookup_phone(flow["phone"])
    saved = flow.get("phone_candidate", flow.get("candidate", {}))
    if (
        customer is None
        or customer.pk != saved.get("id")
        or customer.revision != saved.get("revision")
    ):
        raise ValidationError("Customer details changed. Please start again.")
    return customer


def other_customer(flow):
    saved = flow["other_candidate"]
    customer = Customer.objects.filter(pk=saved["id"], revision=saved["revision"]).first()
    if customer is None or customer.email.casefold() != flow["conflict_email"].casefold():
        raise ValidationError("Customer details changed. Please start again.")
    return customer


def associate(flow, customer, matched_by):
    flow.update(
        candidate={"id": customer.pk, "revision": customer.revision},
        proof=profile_proof(customer, flow["key"]),
        verification_mode="fourth_match",
        verified_by=matched_by,
        stage="details" if customer.email else "email",
    )
    for key in (
        "contact",
        "lookup_note",
        "candidate_name",
        "fourth_confirmation",
        "recovery_notice",
        "recovery_failed",
        "verification_error",
    ):
        flow.pop(key, None)


@transaction.atomic
def conflict_notice(flow, original, other, mode):
    # One persistent owner notice per flow/profile pair, including repeat posts.
    # Use a digest rather than storing the browser flow key in operator content.
    contact_lock()
    flow_ref = hashlib.sha256(flow["key"].encode()).hexdigest()
    notice, created = OwnerNotice.objects.get_or_create(
        customer=original,
        details__kind="booking_profile_conflict",
        details__flow_ref=flow_ref,
        details__email_customer_id=other.pk,
        defaults={
            "subject": "Customer verification details match different profiles",
            "details": {
                "kind": "booking_profile_conflict",
                "flow_ref": flow_ref,
                "email_customer_id": other.pk,
                "email": other.email,
                "entered_phone": flow["phone"],
                "path": mode,
            },
        },
    )
    if created:
        AuditEvent.objects.create(
            actor=None,
            action="customer.public_profile_conflict",
            record_type="customer",
            record_id=str(original.pk),
            changes={"notice_id": notice.pk, "email_customer_id": other.pk, "path": mode},
        )


def prepare_conflict(flow, original, other, mode):
    conflict_notice(flow, original, other, mode)
    flow.update(
        phone_candidate={"id": original.pk, "revision": original.revision},
        other_candidate={"id": other.pk, "revision": other.revision},
        conflict_email=other.email,
        conflict_mode=mode,
    )


def profile_choice(flow, original, other):
    prepare_conflict(flow, original, other, "both_fields")
    flow["original_proof"] = profile_proof(original, flow["key"])
    flow["stage"] = "profile_choice"
    flow.pop("other_proof", None)
    flow.pop("other_possible_name", None)
    kind = name_match(flow.get("entered_name", ""), other)
    if kind == "exact":
        flow["other_proof"] = profile_proof(other, flow["key"])
    elif kind:
        flow["other_possible_name"] = other.last_name


def finish_original(flow, original, matched_by, kind="exact", other=None):
    if kind == "possible":
        flow.update(
            candidate={"id": original.pk, "revision": original.revision},
            candidate_name=original.last_name,
            stage="name_confirm",
            fourth_confirmation={"matched_by": matched_by, "conflict": bool(other)},
        )
        if other:
            prepare_conflict(flow, original, other, "both_fields")
        return
    if other:
        profile_choice(flow, original, other)
    else:
        associate(flow, original, matched_by)


def stop_conflict(flow, original, other, entered):
    # Email-first path: stop/restart, never display the other stored phone or
    # silently associate either profile. Phone/name match takes precedence.
    if name_match(entered, original):
        message = (
            f"The phone you entered {flow['phone']} matches customer name {original.last_name}, "
            f"but your email address {other.email} matches a different customer. "
            f"Please call/text {ASSISTANCE} for assistance with this booking or start again and enter a different email address."
        )
    elif name_match(entered, other):
        message = (
            f"You entered the name ‘{entered}’ which matches the email address ‘{other.email}’, "
            "however there is a different phone number associated with this customer. "
            f"Please start again with the phone number associated with customer {other.last_name}."
        )
    else:
        message = f"The name you entered ‘{entered}’ doesn't match either customer profile. Please call/text {ASSISTANCE} for assistance."
    flow.update(stage="conflict_stop", conflict_message=message)


def process_initial(flow, data, form):
    original = original_customer(flow)
    entered = data.get("last_name", "").strip()
    address = data.get("email", "").strip().lower()
    flow["entered_name"] = entered
    found = find_email(address)
    kind = name_match(entered, original)
    if found and found.pk != original.pk:
        if entered and kind:
            finish_original(flow, original, "name", kind, other=found)
        else:
            prepare_conflict(flow, original, found, "email_first")
            flow["stage"] = "conflict_name"
        return
    email_matches = found is not None and found.pk == original.pk
    if kind or email_matches:
        matched = "both" if kind and email_matches else "name" if kind else "email"
        finish_original(flow, original, matched, kind if kind else "exact")
    elif entered and not address:
        flow.update(stage="email_lookup", fourth_recovery="name_failed", recovery_failed=False)
    elif address and not entered:
        flow.update(stage="name_retry", recovery_email=address, recovery_failed=False)
    else:
        form.add_error(
            None,
            f"We couldn't match that name or email address to phone number ‘{flow['phone']}’. Please try again or call/text {ASSISTANCE} for assistance.",
        )


def process_choice(flow, form):
    original = original_customer(flow)
    other = other_customer(flow)
    customer_from_flow(flow | {"proof": flow["original_proof"]})
    action = form.data.get("profile_action")
    if action == "original":
        address = form.cleaned_data.get("email", "").strip().lower()
        if find_email(address) is None or not address or original.email.casefold() != address:
            form.add_error(
                "email", f"We couldn't match that email address to phone number ‘{flow['phone']}’."
            )
        else:
            associate(flow, original, "both")
    elif action == "verify_other":
        entered = form.cleaned_data.get("last_name", "").strip()
        kind = name_match(entered, other)
        if not kind:
            form.add_error(
                "last_name",
                f"That name doesn't match our records for email address ‘{other.email}’. Please try again or call/text {ASSISTANCE} for assistance.",
            )
        elif kind == "possible":
            flow["other_entered_name"] = entered
            flow["other_possible_name"] = other.last_name
        else:
            flow["other_proof"] = profile_proof(other, flow["key"])
            flow.pop("other_possible_name", None)
    elif action == "confirm_other" and flow.get("other_possible_name"):
        entered = flow.get("other_entered_name", flow.get("entered_name", ""))
        if not name_match(entered, other):
            raise ValidationError("Customer details changed. Please start again.")
        flow["other_proof"] = profile_proof(other, flow["key"])
        flow.pop("other_possible_name", None)
    elif action == "other" and flow.get("other_proof"):
        verified = customer_from_flow(flow | {"proof": flow["other_proof"]})
        flow["phone"] = verified.phone
        associate(flow, verified, "both")
    else:
        form.add_error(None, "Choose how you would like to proceed.")


def handle(flow, form, stage):
    """Return False for untouched legacy paths; otherwise mutate only this flow."""
    if stage == "name" and flow.get("verification_entry") == "returning_current":
        process_initial(flow, form.cleaned_data, form)
    elif stage == "name_confirm" and flow.get("fourth_confirmation"):
        original = original_customer(flow)
        pending = flow["fourth_confirmation"]
        if not name_match(flow.get("entered_name", ""), original):
            raise ValidationError("Customer details changed. Please start again.")
        if pending["conflict"]:
            profile_choice(flow, original, other_customer(flow))
        else:
            associate(flow, original, pending["matched_by"])
            if pending["matched_by"] == "name":
                flow["verification_mode"] = "name_confirm"
    elif stage == "profile_choice":
        process_choice(flow, form)
    elif stage == "conflict_name":
        original, other = original_customer(flow), other_customer(flow)
        entered = form.cleaned_data["last_name"]
        if name_match(entered, other):
            flow["entered_name"] = entered
            if name_match(entered, original):
                profile_choice(flow, original, other)
            else:
                prepare_recovered(flow, other, other.email)
                flow["entered_name"] = entered
                flow["stage"] = "recovered_confirm"
        else:
            stop_conflict(flow, original, other, entered)
    elif stage == "recovered_name":
        customer = recovered_customer(flow)
        entered = form.cleaned_data["last_name"]
        if not name_match(entered, customer):
            form.add_error(
                "last_name",
                f"That name doesn't match our records for email address ‘{flow['recovery_email']}’. Please try again or call/text {ASSISTANCE} for assistance.",
            )
        else:
            flow.update(entered_name=entered, stage="recovered_confirm")
    elif stage == "recovered_confirm":
        customer = recovered_customer(flow)
        if not name_match(flow.get("entered_name", ""), customer):
            raise ValidationError("Please verify the customer name before continuing.")
        flow["phone"] = customer.phone
        associate(flow, customer, "both")
    elif stage == "name_retry":
        original = original_customer(flow)
        entered = form.cleaned_data["last_name"]
        flow["entered_name"] = entered
        kind = name_match(entered, original)
        if kind:
            finish_original(flow, original, "name", kind)
        else:
            flow["recovery_failed"] = True
            form.add_error(
                None,
                f"We couldn't match the name ‘{entered}’ to phone number ‘{flow['phone']}’. Please try again or call/text {ASSISTANCE} for assistance.",
            )
    elif stage == "email_lookup":
        original = lookup_phone(flow["phone"])
        address = form.cleaned_data["email"].strip().lower()
        if original is None:
            found = find_email(address)
            if found:
                prepare_recovered(flow, found, address)
            else:
                flow["unmatched_email_failed"] = True
                form.add_error(
                    None,
                    f"We couldn't match those details. Please try again or call/text {ASSISTANCE} for help.",
                )
            return True
        is_fourth = (
            flow.get("fourth_recovery") == "name_failed"
            or flow.get("verification_entry") == "returning_current"
        )
        possible = Customer.objects.filter(email__iexact=address).first()
        if not is_fourth and (possible is None or possible.pk == original.pk):
            return False
        found = find_email(address)
        if found and found.pk != original.pk:
            prepare_conflict(flow, original, found, "email_first")
            flow["stage"] = "conflict_name"
        elif found:
            associate(flow, original, "email")
        else:
            flow["recovery_failed"] = True
            form.add_error(
                None,
                f"We couldn't match the email address ‘{address}’ to phone number ‘{flow['phone']}’. Please try again or call/text {ASSISTANCE} for assistance.",
            )
    elif stage == "conflict_stop":
        for key in list(flow):
            if key not in {"key", "session_id", "expires"}:
                flow.pop(key)
        flow["stage"] = "phone"
    else:
        return False
    return True


def choice_context(flow):
    if flow.get("stage") == "recovered_confirm":
        customer = recovered_customer(flow)
        if not name_match(flow.get("entered_name", ""), customer):
            raise ValidationError("Please verify the customer name before continuing.")
        return {"recovered_profile": customer}
    if flow.get("stage") != "profile_choice":
        return {}
    original = original_customer(flow)
    customer_from_flow(flow | {"proof": flow["original_proof"]})
    verified = (
        customer_from_flow(flow | {"proof": flow["other_proof"]})
        if flow.get("other_proof")
        else None
    )
    return {
        "original_phone": original.phone,
        "verified_other_phone": verified.phone if verified else None,
    }
