"""Re-verify the same customer to read an accepted initial purchase only."""

import uuid

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from . import membership_receipt_access as access
from . import public_identity, public_verification
from .forms import normalize_phone
from .public_booking_views import limit
from .public_membership_join import display, fresh
from .public_membership_views import private_view


class ReceiptIdentityForm(public_verification.NameOrEmailForm):
    phone = forms.CharField(
        max_length=40,
        label="Phone number",
        widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(["phone", "last_name", "email"])

    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"])


def advance(flow, form, stage, post):
    if stage != "phone":
        return public_identity.advance(flow, form, post=post)
    # Normal verification stays on one page; uncommon recovery retains the
    # existing explicit spelling, previous-phone and conflicting-profile steps.
    phone_form = public_identity.PhoneForm({"phone": form.cleaned_data["phone"], "visited": "yes"})
    if not phone_form.is_valid():
        raise ValidationError("Check your phone number.")
    step = public_identity.advance(flow, phone_form, post=phone_form.cleaned_data)
    if form.cleaned_data.get("last_name"):
        flow["entered_name"] = form.cleaned_data["last_name"]
    if flow["stage"] == "name":
        identity = public_identity.form_type(flow)(form.cleaned_data)
        if not identity.is_valid():
            raise ValidationError("Enter your last name or email address.")
        step = public_identity.advance(flow, identity, post=post)
    return step


def new_record(receipt):
    return dict(checkout=str(receipt.checkout_id), browser=str(uuid.uuid4()), flow=fresh())


@private_view
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters()
def verify(request):
    try:
        receipt = access.owned_receipt(request)
    except PermissionDenied:
        return display(
            request,
            {},
            receipt_only=True,
            error="This receipt is unavailable in this browser. Please call/text 848-238-5147 for assistance.",
            status=404,
        )
    try:
        access.receipt_for(request)
    except PermissionDenied:
        pass
    else:
        return redirect("public_membership_join_receipt")
    record = request.session.get(access.SESSION_KEY)
    if (
        not record
        or record.get("checkout") != str(receipt.checkout_id)
        or record.get("proof")
        or record.get("flow", {}).get("expires", 0) <= timezone.now().timestamp()
    ):
        record = new_record(receipt)
        request.session[access.SESSION_KEY] = record
    flow = record["flow"]
    try:
        stage = flow["stage"]
        form_type = ReceiptIdentityForm if stage == "phone" else public_identity.form_type(flow)
        if form_type is None or stage in {"contact", "email"}:
            raise ValidationError("Verify the existing customer details to view this receipt.")
        form = form_type(request.POST if request.method == "POST" else None)
        if request.method == "POST":
            if (
                request.POST.get("wizard_key") != flow["key"]
                or request.POST.get("wizard_stage") != stage
            ):
                return display(
                    request,
                    flow,
                    receipt_only=True,
                    form=form_type(),
                    error="This verification changed in another tab. Review these details before continuing.",
                    status=400,
                )
            limit(request, "membership-receipt-verify", 30)
            action = request.POST.get("action")
            if action == "restart":
                request.session[access.SESSION_KEY] = new_record(receipt)
                return redirect("public_membership_receipt_verify")
            if request.POST.get("continue_new"):
                raise ValidationError("Use the existing customer profile for this receipt.")
            if action == "email_recovery":
                if not flow.get("phone"):
                    raise ValidationError("Enter your phone number first.")
                flow["stage"] = "email_lookup"
            elif form.is_valid():
                step = advance(flow, form, stage, request.POST)
                request.session[access.SESSION_KEY] = record
                if step.error:
                    return display(request, flow, receipt_only=True, error=step.error, status=400)
                if step.display:
                    return display(request, flow, receipt_only=True, form=step.form)
                if flow["stage"] in {"details", "email"}:
                    try:
                        access.grant(request, record)
                    except (PermissionDenied, ValidationError):
                        request.session[access.SESSION_KEY] = new_record(receipt)
                        return display(
                            request,
                            request.session[access.SESSION_KEY]["flow"],
                            receipt_only=True,
                            form=ReceiptIdentityForm(),
                            error="Those details don't identify the customer who purchased this membership. Please try again.",
                            status=400,
                        )
                    return redirect("public_membership_join_receipt")
            else:
                return display(request, flow, receipt_only=True, form=form)
            request.session[access.SESSION_KEY] = record
            return redirect("public_membership_receipt_verify")
        return display(request, flow, receipt_only=True, form=form)
    except ValidationError as exc:
        return display(request, flow, receipt_only=True, error=" ".join(exc.messages), status=400)
