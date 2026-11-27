"""Browser-owned initial membership identity and the combined public checkout."""

import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from . import public_identity, public_verification
from . import public_membership_views as payment
from .membership_public_authority import LIFETIME, verified_scope
from .membership_public_checkout import begin
from .membership_records import MembershipPublicAcceptance
from .models import Customer, PaymentSetup
from .public_booking_views import limit


def fresh():
    return dict(key=str(uuid.uuid4()), stage="phone", expires=timezone.now().timestamp() + LIFETIME)


def save(request, flow):
    request.session[payment.INITIAL_SESSION_KEY] = flow


def can_restart(flow):
    checkout_id = flow.get("checkout_id")
    if not checkout_id:
        return True
    return not (
        MembershipPublicAcceptance.objects.filter(checkout_id=checkout_id).exists()
        or PaymentSetup.objects.filter(
            kind="membership",
            actor__isnull=True,
            membership_authorization__request_key=checkout_id,
            state__in=["prepared", "customer_sending", "method_sending", "unknown"],
        ).exists()
    )


def display(request, flow, *, form=None, error=None, status=200, receipt_only=False):
    return render(
        request,
        "core/public_membership_identity.html",
        {
            "flow": flow,
            "form": form,
            "error": error,
            "receipt_only": receipt_only,
            "restart_allowed": bool(flow) and can_restart(flow),
            **(public_verification.choice_context(flow) if form is not None else {}),
        },
        status=status,
    )


@payment.private_view
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters()
def join(request):
    flow = request.session.get(payment.INITIAL_SESSION_KEY)
    if not flow:
        flow = fresh()
        save(request, flow)
    if (request.method == "POST" and request.POST.get("action") == "restart") or (
        request.method == "GET" and request.GET.get("restart") == "1"
    ):
        if request.method == "POST" and request.POST.get("wizard_key") != flow["key"]:
            return display(
                request,
                flow,
                error="This page changed in another tab. Reload before continuing.",
                status=400,
            )
        if not can_restart(flow):
            return display(
                request,
                flow,
                error="An existing purchase or card setup needs review. Please check its payment status or call/text 848-238-5147 before another attempt.",
                status=400,
            )
        flow = fresh()
        save(request, flow)
        return redirect("public_membership_join")
    try:
        if flow.get("checkout_id"):
            try:
                _, record, scope = payment.state(request)
            except PermissionDenied:
                from .membership_receipt_access import owned_receipt

                try:
                    owned_receipt(request)
                except PermissionDenied:
                    pass
                else:
                    return redirect("public_membership_receipt_verify")
                return display(
                    request,
                    flow,
                    error="Your verification expired or customer details changed. Please call/text 848-238-5147 to check an existing purchase or card setup before trying again.",
                    status=400,
                )
            return payment.checkout(request, None, record, scope)
        if timezone.now().timestamp() >= flow.get("expires", 0):
            raise ValidationError("This membership session expired. Please start again.")
        stage = flow["stage"]
        form_type = public_identity.form_type(flow)
        if form_type is None:
            raise ValidationError("Please start again to verify your customer details.")
        args = (
            {
                "phone": flow["phone"],
                "restart_url": reverse("public_membership_join") + "?restart=1",
            }
            if stage in {"contact", "email"}
            else {}
        )
        form = form_type(request.POST if request.method == "POST" else None, **args)
        if request.method == "POST":
            if (
                request.POST.get("wizard_key") != flow["key"]
                or request.POST.get("wizard_stage") != stage
            ):
                return display(
                    request,
                    flow,
                    form=form_type(**args),
                    error="This page changed in another tab. Review these details before continuing.",
                    status=400,
                )
            limit(request, "membership-purchase-identity", 40)
            if request.POST.get("action") == "email_recovery":
                if not flow.get("phone"):
                    raise ValidationError("Enter your phone number first.")
                flow["stage"] = "email_lookup"
                save(request, flow)
                return redirect("public_membership_join")
            if stage == "contact":
                form.is_valid()
                if form.cleaned_data.get("last_name"):
                    flow["entered_name"] = form.cleaned_data["last_name"]
                    save(request, flow)
            if form.is_valid():
                step = public_identity.advance(flow, form, post=request.POST)
                save(request, flow)
                if step.error:
                    return display(request, flow, error=step.error, status=400)
                if step.display:
                    return display(request, flow, form=step.form)
                if flow["stage"] == "details":
                    try:
                        proof = begin(flow)
                    except ValidationError as exc:
                        flow["stage"] = stage
                        save(request, flow)
                        form.add_error(None, " ".join(exc.messages))
                        return display(request, flow, form=form)
                    scope = verified_scope(proof)
                    payment.save_state(request, scope["checkout_record"], {"proof": proof})
                    flow["checkout_id"] = str(scope["request_key"])
                    save(request, flow)
                return redirect("public_membership_join")
        return display(request, flow, form=form)
    except (ValidationError, Customer.DoesNotExist) as exc:
        error = (
            " ".join(exc.messages)
            if isinstance(exc, ValidationError)
            else "Customer details changed. Please start again."
        )
        return display(request, flow, error=error, status=400)
