"""Staff browser-bound secure card entry for an accepted membership selection."""

import json

from django import forms
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_POST

from .active_membership_views import PurchaseForm, check_enabled
from .membership_card_setup import authorize_flow, choose_saved, identity, make_flow, source
from .membership_records import MembershipCardAuthorization
from .membership_sales import offer
from .payments.gateway import ProviderFailure
from .payments.models import PaymentMethod, PaymentSetup
from .payments.setup import exchange
from .permissions import staff_permission
from .public_booking_views import limit

SESSION_KEY = "membership_card_flows"


class CardInput(forms.Form):
    setup_key = forms.UUIDField(required=False)
    method = forms.UUIDField(required=False)
    nonce = forms.CharField(max_length=26, required=False)
    expiry_month = forms.IntegerField(min_value=1, max_value=12, required=False)
    expiry_year = forms.IntegerField(min_value=2020, max_value=9999, required=False)
    retention_choice = forms.ChoiceField(required=False, choices=[("yes", "Yes"), ("no", "No")])

    def clean(self):
        data = super().clean()
        if data.get("method"):
            if data.get("nonce"):
                raise forms.ValidationError("Choose a saved card or enter a new card.")
        elif not all(
            data.get(name)
            for name in ("setup_key", "nonce", "expiry_month", "expiry_year", "retention_choice")
        ):
            raise forms.ValidationError(
                "Complete the secure card fields and choose whether to keep this card for future visits."
            )
        return data


def current_flow(request, data):
    flows = request.session.get(SESSION_KEY, {})
    key = str(data["request_key"])
    previous = flows.get(key)
    if previous:
        authorize_flow(previous, request.user)
        if (
            previous["customer_id"] != data["customer"].pk
            or previous["customer_revision"] != data["customer"].revision
        ):
            raise ValidationError(
                "Start a new membership purchase before changing this card session's customer."
            )
    flow = make_flow(
        actor=request.user,
        customer=data["customer"],
        request_key=key,
        offer=data["offer"],
        expires=previous["expires"] if previous else None,
    )
    flows = {
        key: value
        for key, value in flows.items()
        if value.get("expires", 0) >= timezone.now().timestamp()
    }
    # Bound unrelated old browser tabs without extending an accepted session.
    if key not in flows and len(flows) >= 10:
        raise ValidationError(
            "Close an older membership purchase before starting another card session."
        )
    flows[key] = flow
    request.session[SESSION_KEY] = flows
    request.session.save()  # Persist recovery scope before any provider request.
    return flow


def saved_response(authority):
    method = source(authority)
    return JsonResponse(
        dict(
            state="saved",
            authorization_id=str(authority.pk),
            method_id=str(method.pk),
            brand=method.brand,
            last_four=method.last_four,
            offer_fingerprint=authority.offer_fingerprint,
        )
    )


@staff_permission("core.add_membershippurchase")
@staff_permission("core.view_customer")
@staff_permission("core.collect_payment")
@require_POST
@sensitive_post_parameters()
@sensitive_variables()
def setup_card(request):
    check_enabled()
    try:
        limit(request, "membership-card-setup", 10)
        if len(request.body) > 8192:
            raise ValidationError("Use the secure membership card form.")
        payload = json.loads(request.body)
        if not isinstance(payload, dict) or set(payload) - {"purchase", *CardInput.base_fields}:
            raise ValidationError("Use the secure membership card form.")
        purchase_data = payload.pop("purchase", None)
        if not isinstance(purchase_data, dict) or set(purchase_data) - set(
            PurchaseForm.base_fields
        ):
            raise ValidationError("Use the current membership purchase form.")
        form = PurchaseForm(purchase_data, owner=request.user.is_superuser, actor=request.user)
        for name in ("method", "card_authorization", "verified_received", "send_confirmation"):
            form.fields.pop(name, None)
        card = CardInput(payload)
        if not form.is_valid() or not card.is_valid():
            raise ValidationError(
                "Review the membership details and complete the secure card fields, including the future-use choice."
            )
        data = form.cleaned_data
        current = offer(actor=request.user, **form.offer_values())
        if data["accepted"] is not True or current["fingerprint"] != data["reviewed"]:
            raise ValidationError(
                "Review and accept the current membership terms before saving this card."
            )
        if current["comped"] or (
            current["billing"] == "prepaid" and current["expected_method"] != "card"
        ):
            raise ValidationError("This selected membership payment does not require a card.")
        flow = current_flow(request, data | {"offer": current})
        values = card.cleaned_data
        if values["method"]:
            return saved_response(
                choose_saved(
                    actor=request.user, flow=flow, method_id=values["method"], accepted=True
                )
            )
        flow["setup_key"] = str(values["setup_key"])
        flows = request.session.get(SESSION_KEY, {})
        flows[flow["key"]] = flow
        request.session[SESSION_KEY] = flows
        request.session.save()
        setup = exchange(
            flow=flow,
            actor=request.user,
            request_key=values["setup_key"],
            nonce=values["nonce"],
            expiry_month=values["expiry_month"],
            expiry_year=values["expiry_year"],
            retain=values["retention_choice"] == "yes",
            payment_accepted=True,
            cancellation_accepted=False,
        )
        if setup.state == "succeeded":
            return saved_response(setup.membership_authorization)
        return JsonResponse(
            dict(
                state="review",
                error="We couldn't confirm whether the membership card was saved. Check this setup before trying another card.",
                status_url=reverse("membership_card_status", args=[setup.pk]),
            ),
            status=202,
        )
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)
    except (
        ProviderFailure,
        PaymentMethod.DoesNotExist,
        ValueError,
        TypeError,
        KeyError,
    ):
        return JsonResponse(
            {
                "error": "Card setup could not be completed. Review the current membership selection and secure card details, or call/text 848-238-5147."
            },
            status=400,
        )


@staff_permission("core.add_membershippurchase")
@staff_permission("core.view_customer")
@staff_permission("core.collect_payment")
@require_GET
def setup_status(request, setup_id):
    try:
        setup = PaymentSetup.objects.select_related("membership_authorization", "method").get(
            pk=setup_id, kind="membership", actor=request.user
        )
        authority = setup.membership_authorization
        flow = request.session.get(SESSION_KEY, {}).get(str(authority.request_key))
        authorize_flow(flow, request.user)
        if identity(flow)[0] != setup.flow_hash:
            raise ValidationError("Use the original membership card session.")
        if setup.state == "succeeded":
            return saved_response(authority)
        return JsonResponse(
            dict(
                state="review",
                error="This card setup still needs review. No membership payment has been requested.",
            ),
            status=202,
        )
    except (
        ValidationError,
        PaymentSetup.DoesNotExist,
        MembershipCardAuthorization.DoesNotExist,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
    ):
        return JsonResponse(
            {"error": "This membership card setup is unavailable in the current browser session."},
            status=404,
        )
