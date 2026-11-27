"""Verified initial purchase/private renewal; no broad public account access."""

import json
from functools import wraps

from django import forms
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.cache import add_never_cache_headers
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .active_membership_views import PurchaseForm, display_offer
from .membership_card_setup import available_methods, identity, make_flow
from .membership_card_views import CardInput, saved_response
from .membership_public_authority import (
    acceptance_filter,
    resolve_link,
    submit,
    verified_scope,
    verify_identity,
)
from .membership_records import MembershipPublicAcceptance
from .membership_renewals import renewal_details
from .membership_sales import installment_paid, membership_status, offer
from .models import Customer, PaymentMethod, PaymentSetup
from .payments.amounts import ZERO
from .payments.gateway import ProviderFailure
from .payments.invoices import received
from .payments.setup import exchange
from .public_booking_views import limit

SESSION_KEY = "private_membership_renewals"
INITIAL_SESSION_KEY = "initial_membership_identity"


def private_view(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not settings.MEMBERSHIP_SALES_ENABLED or settings.DESIGN_REVIEW_ONLY:
            raise Http404
        if settings.RECOVERY_HOLD:
            response = render(
                request,
                "core/public_membership_renewal.html",
                {
                    "error": "Membership payments are temporarily paused. Please call/text 848-238-5147 for assistance."
                },
                status=503,
            )
        else:
            response = view(request, *args, **kwargs)
        add_never_cache_headers(response)
        # Keep renewal tokens out of cross-origin requests while preserving the
        # browser's same-origin Origin/Referer evidence for Django CSRF checks.
        response["Referrer-Policy"] = "same-origin"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response

    return wrapped


class VerifyForm(forms.Form):
    phone = forms.CharField(max_length=30, label="Phone number")
    last_name = forms.CharField(max_length=120, label="Last name")


def public_url(token, kind="checkout", *, setup_id=None):
    names = {
        "checkout": "renewal",
        "offer": "offer",
        "card": "card",
        "status": "card_status",
        "receipt": "receipt",
    }
    if token is None:
        name = "public_membership_join" + ("" if kind == "checkout" else "_" + names[kind])
        kwargs = {}
    else:
        name = "public_membership_" + names[kind]
        kwargs = {"token": token}
    if setup_id is not None:
        kwargs["setup_id"] = setup_id
    return reverse(name, kwargs=kwargs)


def state(request, token=None):
    if token is None:
        checkout_id = request.session.get(INITIAL_SESSION_KEY, {}).get("checkout_id")
        record = request.session.get(SESSION_KEY, {}).get(str(checkout_id), {})
        scope = verified_scope(record.get("proof"))
        source = scope.get("checkout_record")
        if source is None or str(source.pk) != checkout_id:
            raise PermissionDenied
    else:
        source = resolve_link(token)
        record = request.session.get(SESSION_KEY, {}).get(str(source.pk), {})
        scope = verified_scope(record.get("proof"))
        if scope.get("link_record") != source:
            raise PermissionDenied
    return source, record, scope


def save_state(request, link, record):
    records = request.session.get(SESSION_KEY, {})
    if str(link.pk) not in records and len(records) >= 10:
        records.pop(next(iter(records)))
    records[str(link.pk)] = record
    request.session[SESSION_KEY] = records
    request.session.save()


def method_flow(scope, proof):
    return dict(
        purpose="membership",
        key=str(scope["request_key"]),
        staff_actor=None,
        public_authority=proof,
        customer_id=scope["customer"],
        customer_revision=scope["revision"],
        prior_id=scope["prior"],
        operation=scope["operation"],
        expected_method="card",
        expires=scope["expires"],
    )


class PublicPurchaseForm(PurchaseForm):
    def __init__(self, *args, scope, proof, **kwargs):
        bound = (args[0] if args else kwargs.get("data")) or {}
        if scope["operation"] == "purchase" and bound.get("prior_id") not in (None, ""):
            raise ValidationError("Use the current membership purchase form.")
        self.scope = scope
        self.proof = proof
        initial = dict(customer=scope["customer"], request_key=scope["request_key"])
        super().__init__(
            *args,
            owner=False,
            prior=scope["link_record"].prior if scope["operation"] == "renewal" else None,
            operation=scope["operation"],
            initial=initial,
            **kwargs,
        )
        details = (
            renewal_details(scope["link_record"].prior) if scope["operation"] == "renewal" else None
        )
        self.renewal_details = details
        if details and details["available_places"] <= 0:
            raise ValidationError(
                "These membership places already have a renewal recorded. Please call/text MonkeyDo if you need assistance."
            )
        self.fields["customer"].queryset = Customer.objects.filter(pk=scope["customer"])
        self.fields["customer"].widget = forms.HiddenInput()
        self.fields["method"].queryset = available_methods(method_flow(scope, proof)).order_by(
            "last_four", "pk"
        )
        if not self.fields["method"].queryset.filter(pk=self.initial.get("method")).exists():
            candidates = list(self.fields["method"].queryset[:2])
            if len(candidates) == 1:
                self.initial["method"] = candidates[0].pk
        self.fields["method"].label = "Your membership card"
        self.fields.pop("credit_amount", None)
        self.fields["kind"].label = "Membership type"
        self.fields["places"] = forms.IntegerField(
            min_value=1,
            max_value=details["available_places"] if details else 2147483647,
            label="Number of memberships",
            initial=details["available_places"] if details else 1,
        )
        self.fields["expected_method"].choices = [("card", "Credit card")]
        self.fields["expected_method"].initial = "card"
        self.fields["expected_method"].widget = forms.HiddenInput()
        self.fields["verified_received"].widget = forms.HiddenInput()
        self.fields["accepted"].label = "I accept the membership terms and the payments shown above"

    def clean(self):
        data = super().clean()
        if self.data.get("credit_amount") not in (None, "", "0", "0.00"):
            raise ValidationError("Ask staff to review customer credit for this purchase.")
        if set(self.data) - {
            *PurchaseForm.base_fields,
            "csrfmiddlewaretoken",
            "action",
            "member_retain",
        }:
            raise ValidationError("Use the secure membership form.")
        if self.errors:
            return data
        if (
            data["customer"].pk != self.scope["customer"]
            or data["request_key"] != self.scope["request_key"]
            or data["prior_id"] != self.scope["prior"]
            or data["operation"] != self.scope["operation"]
        ):
            raise ValidationError(
                "This membership session changed. Reload and verify your details again."
            )
        for key in ("minimum_override", "comped"):
            if forms.BooleanField(required=False).clean(self.data.get(key)):
                raise ValidationError("Please contact MonkeyDo for a membership exception.")
        return data

    def values(self):
        return {
            key: self.cleaned_data[key]
            for key in ("kind", "places", "months", "billing", "starts_on")
        }


def render_checkout(request, token, record, scope, form, data=None):
    card_flow = record.get("card_flow", {})
    return render(
        request,
        "core/public_membership_renewal.html",
        dict(
            form=form,
            customer=scope["customer_record"],
            prior=scope["link_record"].prior if scope["operation"] == "renewal" else None,
            prior_ends_on=form.renewal_details["ends_on"] if form.renewal_details else None,
            initial_purchase=scope["operation"] == "purchase",
            membership_offer_url=public_url(token, "offer"),
            offer=display_offer(data),
            token=token,
            membership_card_public=True,
            membership_card_start_new=scope["operation"] == "purchase"
            and not form.fields["method"].queryset.exists(),
            membership_card_endpoint=public_url(token, "card"),
            membership_card_configured=bool(
                settings.PAYMENT_SANDBOX_ENABLED
                and settings.BANQUEST_API_SOURCE_KEY
                and settings.BANQUEST_TOKENIZATION_PUBLIC_KEY.startswith("pk_")
            ),
            membership_card_public_key=settings.BANQUEST_TOKENIZATION_PUBLIC_KEY,
            membership_card_status_url=public_url(token, "status", setup_id=card_flow["setup_key"])
            if card_flow.get("setup_key")
            else "",
        ),
    )


@private_view
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters()
def renewal(request, token):
    try:
        link = resolve_link(token)
    except ValidationError as exc:
        return render(
            request,
            "core/public_membership_renewal.html",
            {"error": " ".join(exc.messages)},
            status=404,
        )
    if request.method == "POST" and request.POST.get("action") == "verify":
        form = VerifyForm(request.POST)
        if form.is_valid():
            try:
                limit(request, "membership-renewal-verify", 8)
                proof = verify_identity(token=token, **form.cleaned_data)
                save_state(request, link, {"proof": proof})
                return redirect(public_url(token))
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
        return render(request, "core/public_membership_renewal.html", {"verification_form": form})
    try:
        link, record, scope = state(request, token)
    except ValidationError as exc:
        return render(
            request,
            "core/public_membership_renewal.html",
            {"error": " ".join(exc.messages)},
            status=404,
        )
    except PermissionDenied:
        return render(
            request, "core/public_membership_renewal.html", {"verification_form": VerifyForm()}
        )
    return checkout(request, token, record, scope)


def checkout(request, token, record, scope):
    if MembershipPublicAcceptance.objects.filter(**acceptance_filter(scope)).exists():
        return redirect(public_url(token, "receipt"))
    try:
        form = PublicPurchaseForm(
            request.POST if request.method == "POST" else None, scope=scope, proof=record["proof"]
        )
        data = None
        if request.method == "POST" and form.is_valid():
            data = offer(actor=None, authority=record["proof"], **form.offer_values())
            if request.POST.get("action") == "confirm":
                submit(
                    proof=record["proof"],
                    reviewed=form.cleaned_data["reviewed"],
                    accepted=form.cleaned_data["accepted"],
                    card_authorization_id=form.cleaned_data["card_authorization"],
                    method_id=form.cleaned_data["method"].pk
                    if form.cleaned_data["method"]
                    else None,
                    **form.values(),
                )
                return redirect(public_url(token, "receipt"))
        return render_checkout(request, token, record, scope, form, data)
    except ValidationError as exc:
        if "form" in locals():
            form.add_error(None, " ".join(exc.messages))
            return render_checkout(request, token, record, scope, form)
        return render(
            request, "core/public_membership_renewal.html", {"error": " ".join(exc.messages)}
        )


@private_view
@require_POST
def live_offer(request, token=None):
    try:
        _, record, scope = state(request, token)
        form = PublicPurchaseForm(request.POST, scope=scope, proof=record["proof"])
        for key in ("method", "card_authorization"):
            form.fields.pop(key, None)
        if not form.is_valid():
            raise ValidationError(
                " ".join(str(error) for errors in form.errors.values() for error in errors)
            )
        data = offer(actor=None, authority=record["proof"], **form.offer_values())
        return JsonResponse(
            dict(
                html=render_to_string(
                    "core/partials/membership_offer.html",
                    {"offer": display_offer(data)},
                    request=request,
                ),
                fingerprint=data["fingerprint"],
                terms=data["terms"],
                starts_on=data["starts_on"],
                minimum_months=data["minimum_months"],
                cards=[
                    dict(id=str(card.pk), label=f"{card.brand} ending in {card.last_four}")
                    for card in available_methods(method_flow(scope, record["proof"]))
                ],
            )
        )
    except (ValidationError, PermissionDenied) as exc:
        return JsonResponse(
            {
                "error": " ".join(exc.messages)
                if isinstance(exc, ValidationError)
                else "Your verification expired. Reload this page to verify your details again."
            },
            status=400,
        )


@private_view
@require_POST
@sensitive_post_parameters()
@sensitive_variables()
def setup_card(request, token=None):
    try:
        link, record, scope = state(request, token)
        limit(request, "public-membership-card", 10)
        if MembershipPublicAcceptance.objects.filter(**acceptance_filter(scope)).exists():
            raise ValidationError(
                "A membership purchase is already recorded. Open your confirmation before starting another purchase."
            )
        if len(request.body) > 8192:
            raise ValidationError("Use the secure card form.")
        payload = json.loads(request.body)
        if not isinstance(payload, dict) or set(payload) - {"purchase", *CardInput.base_fields}:
            raise ValidationError("Use the secure card form.")
        purchase_data = payload.pop("purchase", None)
        if not isinstance(purchase_data, dict) or set(purchase_data) - set(
            PurchaseForm.base_fields
        ):
            raise ValidationError("Use the current membership form.")
        form = PublicPurchaseForm(purchase_data, scope=scope, proof=record["proof"])
        for key in ("method", "card_authorization"):
            form.fields.pop(key, None)
        card = CardInput(payload)
        if not form.is_valid() or not card.is_valid():
            raise ValidationError(
                "Review your membership selection and complete the secure card fields."
            )
        data = offer(actor=None, authority=record["proof"], **form.offer_values())
        if (
            form.cleaned_data["accepted"] is not True
            or form.cleaned_data["reviewed"] != data["fingerprint"]
        ):
            raise ValidationError("Review and accept the current terms before saving your card.")
        old = record.get("card_flow", {})
        flow = make_flow(
            actor=None,
            authority=record["proof"],
            customer=scope["customer_record"],
            request_key=scope["request_key"],
            offer=data,
            expires=old.get("expires"),
        )
        values = card.cleaned_data
        if values["method"]:
            from .membership_card_setup import choose_saved

            record["card_flow"] = flow
            save_state(request, link, record)
            return saved_response(
                choose_saved(actor=None, flow=flow, method_id=values["method"], accepted=True)
            )
        flow["setup_key"] = str(values["setup_key"])
        record["card_flow"] = flow
        save_state(request, link, record)
        result = exchange(
            actor=None,
            flow=flow,
            request_key=values["setup_key"],
            nonce=values["nonce"],
            expiry_month=values["expiry_month"],
            expiry_year=values["expiry_year"],
            retain=values["retention_choice"] == "yes",
            payment_accepted=True,
            cancellation_accepted=False,
        )
        if result.state == "succeeded":
            return saved_response(result.membership_authorization)
        return JsonResponse(
            dict(
                state="review",
                error="We couldn't confirm whether your card was saved. Check card setup before another attempt.",
            ),
            status=202,
        )
    except PermissionDenied:
        return JsonResponse(
            {"error": "Your verification expired. Reload this page to verify your details again."},
            status=400,
        )
    except (
        ValidationError,
        ProviderFailure,
        PaymentMethod.DoesNotExist,
        ValueError,
        TypeError,
        KeyError,
    ) as exc:
        return JsonResponse(
            {
                "error": " ".join(exc.messages)
                if isinstance(exc, ValidationError)
                else "Card setup could not be confirmed. Please call/text 848-238-5147 before another attempt."
            },
            status=400,
        )


@private_view
@require_GET
def setup_status(request, setup_id, token=None):
    try:
        _, record, scope = state(request, token)
        flow = record.get("card_flow")
        saved = PaymentSetup.objects.select_related("membership_authorization", "method").get(
            pk=setup_id,
            kind="membership",
            actor__isnull=True,
            flow_hash=identity(flow)[0],
            membership_authorization__request_key=scope["request_key"],
        )
        if saved.state == "succeeded":
            return saved_response(saved.membership_authorization)
        return JsonResponse(
            dict(
                state="review",
                error="This card setup still needs review. No membership payment has been requested.",
            ),
            status=202,
        )
    except (
        ValidationError,
        PermissionDenied,
        PaymentSetup.DoesNotExist,
        ValueError,
        TypeError,
        AttributeError,
    ):
        return JsonResponse(
            {"error": "This card setup is unavailable in the current membership session."},
            status=404,
        )


@private_view
@require_GET
def receipt(request, token=None):
    acceptance = None
    receipt_reverified = False
    try:
        link, _, scope = state(request, token)
    except (PermissionDenied, ValidationError):
        if token is not None:
            return redirect(public_url(token))
        from .membership_receipt_access import owned_receipt, receipt_for

        try:
            acceptance = receipt_for(request)
            receipt_reverified = True
        except PermissionDenied:
            try:
                owned_receipt(request)
            except PermissionDenied:
                return redirect(public_url(token))
            return redirect("public_membership_receipt_verify")
    if acceptance is None:
        acceptance = (
            MembershipPublicAcceptance.objects.select_related(
                "purchase__membership", "purchase__customer"
            )
            .filter(**acceptance_filter(scope))
            .first()
        )
    if not acceptance:
        return redirect(public_url(token))
    member = acceptance.purchase
    from .membership_cancellations import plan_paid

    cancellation = member.cancellations.order_by("-created_at").first()
    refund_remaining = (
        sum((plan.amount - plan_paid(plan) for plan in cancellation.refund_plans.all()), ZERO)
        if cancellation
        else ZERO
    )
    item = member.installments.select_related("invoice__sale").first()
    op = item.invoice.sale.operations.filter(kind="receipt").order_by("requested_at").last()
    from .customer_credit import applied

    funds, credit_funds = ZERO, ZERO
    for installment in member.installments.select_related("invoice__sale"):
        if hasattr(installment, "invoice"):
            funds += received(installment.invoice.sale)
            credit_funds += applied(installment.invoice.sale)
    return render(
        request,
        "core/public_membership_renewal.html",
        dict(
            receipt=member,
            initial_purchase=token is None,
            receipt_reverified=receipt_reverified,
            paid=installment_paid(item),
            money_received=funds,
            credit_applied=credit_funds,
            payment_state=op.state if op else "ready",
            status=membership_status(member),
            cancellation=cancellation,
            refund_remaining=refund_remaining,
        ),
    )
