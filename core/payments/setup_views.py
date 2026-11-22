"""Session-bound provider-hosted card setup; never accepts raw card data."""

import json
import uuid

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_POST

from core.public_booking_views import current, limit, save

from .gateway import ProviderFailure
from .models import PaymentMethod, PaymentSetup
from .policy import VERSION
from .setup import choose_saved, exchange, flow_identity, selected_consent


class SetupForm(forms.Form):
    wizard_key = forms.UUIDField()
    wizard_stage = forms.CharField(max_length=30)
    policy_version = forms.CharField(max_length=60)
    request_key = forms.UUIDField(required=False)
    nonce = forms.CharField(max_length=26, required=False)
    expiry_month = forms.IntegerField(min_value=1, max_value=12, required=False)
    expiry_year = forms.IntegerField(min_value=2020, max_value=9999, required=False)
    method = forms.UUIDField(required=False)
    retain = forms.BooleanField(required=False)
    agree_payment = forms.BooleanField()
    agree_cancellation = forms.BooleanField()

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        if data.get("method"):
            if data.get("nonce"):
                raise forms.ValidationError("Choose a saved card or enter a new card.")
        elif not all(
            data.get(k) is not None and data.get(k) != ""
            for k in ("request_key", "nonce", "expiry_month", "expiry_year")
        ):
            raise forms.ValidationError("Complete the secure card entry.")
        return data


@require_POST
@sensitive_post_parameters()
@sensitive_variables()
def setup_card(request, *, reader=current, writer=save, actor=None):
    if not settings.PAYMENT_SANDBOX_ENABLED:
        return JsonResponse({"error": "Card setup is unavailable."}, status=404)
    try:
        flow = reader(request)
        if flow.get("workflow") != "integrated_v1" or flow.get("stage") not in {
            "details",
            "review",
            "card",
        }:
            raise ValidationError("Return to the current integrated booking before card setup.")
        flow_identity(flow)
        limit(request, "card-setup", 10)
        if len(request.body) > 4096:
            raise ValidationError("Use the secure card-entry form.")
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) - set(SetupForm.base_fields):
            raise ValidationError("Use the secure card-entry form.")
        # Primary-card customers accept the displayed payment terms through the
        # explicit Save action; alternate methods retain their separate checkbox.
        if not actor and flow.get("details", {}).get("expected_method") == "card":
            data["agree_payment"] = True
        form = SetupForm(data)
        if not form.is_valid():
            if any(name in form.errors for name in ("expiry_month", "expiry_year")):
                explanation = (
                    "Please check the expiration month and year in the secure card fields."
                )
            elif any(name in form.errors for name in ("agree_payment", "agree_cancellation")):
                explanation = "Please accept the applicable payment and cancellation policies before saving your card."
            else:
                explanation = "Please complete the card number, expiration date and security code in the secure fields."
            return JsonResponse({"error": explanation}, status=400)
        values = form.cleaned_data
        if (
            str(values["wizard_key"]) != flow["key"]
            or values["wizard_stage"] != flow["stage"]
            or values["policy_version"] != VERSION
        ):
            raise ValidationError("The booking or payment policy changed. Please reload this page.")
        if values.get("method"):
            accepted = choose_saved(
                flow=flow,
                method_id=values["method"],
                payment_accepted=True,
                cancellation_accepted=True,
                actor=actor,
            )
        else:
            flow["payment_setup_key"] = str(values["request_key"])
            writer(request, flow)
            request.session.save()  # Durable recovery pointer before provider I/O.
            result = exchange(
                flow=flow,
                request_key=values["request_key"],
                nonce=values["nonce"],
                expiry_month=values["expiry_month"],
                expiry_year=values["expiry_year"],
                retain=values["retain"],
                payment_accepted=True,
                cancellation_accepted=True,
                actor=actor,
            )
            if result.state != "succeeded":
                return JsonResponse(
                    {
                        "state": "review",
                        "error": "We could not confirm card setup. Please call/text 848-238-5147 for assistance before trying again.",
                    },
                    status=202,
                )
            accepted = result.consent
        flow.pop("payment_method_changed", None)
        from core.models import AuditEvent

        AuditEvent.objects.get_or_create(
            action="payment.policy_accepted",
            record_type="payment_consent",
            record_id=str(accepted.pk),
            defaults={
                "actor": actor,
                "changes": {
                    "expected_method": flow.get("details", {}).get("expected_method"),
                    "policy_version": VERSION,
                },
            },
        )
        flow["payment_consent"] = str(accepted.pk)
        flow["payment_consent_method"] = flow.get("details", {}).get("expected_method")
        writer(request, flow)
        return JsonResponse(
            {
                "state": "saved",
                "brand": accepted.method.brand,
                "last_four": accepted.method.last_four,
                "consent_id": str(accepted.pk),
            }
        )
    except ValidationError as error:
        public_error = (
            error.message
            if getattr(error, "code", "")
            in {"expired_saved_method", "unusable_saved_method", "entered_card_expiry"}
            else "Card setup could not be completed for this booking. Please review your details or call/text 848-238-5147."
        )
        return JsonResponse({"error": public_error}, status=400)
    except (PaymentMethod.DoesNotExist, ValueError, TypeError, KeyError):
        return JsonResponse(
            {
                "error": "Card setup could not be completed for this booking. Please review your details or call/text 848-238-5147."
            },
            status=400,
        )
    except ProviderFailure:
        return JsonResponse(
            {"error": "Card setup is temporarily unavailable. Please call/text 848-238-5147."},
            status=503,
        )


def card_context(flow):
    from django.db.models import Q

    from .policy import (
        BACKUP_CANCELLATION,
        BACKUP_PAYMENT,
        BACKUP_RETENTION,
        CANCELLATION,
        CANCELLATION_SCOPE,
        PAYMENT,
        RETENTION,
        VERSION,
    )
    from .setup import reusable_methods

    method = flow.get("details", {}).get("expected_method", "card")
    names = {
        "card": "credit card",
        "cash": "cash",
        "check": "check",
        "zelle": "Zelle",
        "gift_card": "gift card",
    }
    try:
        accepted = selected_consent(flow)
    except ValidationError:
        accepted = None
    methods = reusable_methods(flow)
    if flow.get("payment_method_changed") and flow.get("payment_setup_key"):
        previous = PaymentSetup.objects.filter(
            pk=flow["payment_setup_key"], flow_hash=flow_identity(flow)[0], state="succeeded"
        ).first()
        if previous and previous.method_id:
            methods = PaymentMethod.objects.filter(
                Q(pk__in=methods.values("pk")) | Q(pk=previous.method_id), state="active"
            )
    return {
        "card_primary": method == "card",
        "card_backup_payment": BACKUP_PAYMENT,
        "card_backup_retention": BACKUP_RETENTION,
        "card_backup_cancellation": BACKUP_CANCELLATION,
        "card_method_name": names.get(method, method),
        "card_is_zelle": method == "zelle",
        "card_ready": accepted is not None,
        "card_accepted_consent": str(accepted.pk) if accepted else "",
        "card_accepted_last_four": accepted.method.last_four if accepted else "",
        "card_public_booking": not bool(flow.get("staff_actor")),
        "card_setup_key": uuid.uuid4()
        if flow.get("payment_method_changed")
        else (flow.get("payment_setup_key") or uuid.uuid4()),
        "card_endpoint": reverse("customer_card_setup"),
        "card_status_url": reverse("customer_card_status", args=[flow["payment_setup_key"]])
        if flow.get("payment_setup_key") and not flow.get("payment_method_changed")
        else "",
        "card_methods": methods,
        "card_policy_version": VERSION,
        "card_payment_policy": PAYMENT,
        "card_retention_policy": RETENTION,
        "card_cancellation_policy": CANCELLATION,
        "card_cancellation_scope": CANCELLATION_SCOPE,
        "card_public_key": settings.BANQUEST_TOKENIZATION_PUBLIC_KEY,
        "card_configured": bool(
            settings.PAYMENT_SANDBOX_ENABLED
            and settings.BANQUEST_API_SOURCE_KEY
            and settings.BANQUEST_TOKENIZATION_PUBLIC_KEY.startswith("pk_")
        ),
    }


@require_GET
def setup_status(request, setup_id, *, reader=current, writer=save):
    if not settings.PAYMENT_SANDBOX_ENABLED:
        return JsonResponse({"error": "Card setup is unavailable."}, status=404)
    try:
        flow = reader(request)
        if flow.get("stage") not in {"details", "waiver", "card", "review"}:
            raise ValidationError("Return to the current booking before checking card setup.")
        digest, _ = flow_identity(flow)
        setup = PaymentSetup.objects.select_related("method").get(pk=setup_id, flow_hash=digest)
        if setup.state == "succeeded":
            if flow.get("payment_method_changed"):
                return JsonResponse(
                    {
                        "state": "review",
                        "error": "Your card was saved. Choose it and accept the policies for your selected payment method.",
                    },
                    status=409,
                )
            accepted = setup.consent
            if setup.method.state != "active":
                raise ValidationError("This payment method is no longer available.")
            flow["payment_consent"] = str(accepted.pk)
            writer(request, flow)
            return JsonResponse(
                {
                    "state": "saved",
                    "brand": setup.method.brand,
                    "last_four": setup.method.last_four,
                    "consent_id": str(accepted.pk),
                }
            )
        return JsonResponse(
            {
                "state": "review",
                "error": "Card setup is still being checked. Please call/text 848-238-5147 if you need assistance.",
            },
            status=202,
        )
    except (ValidationError, PaymentSetup.DoesNotExist, ValueError, KeyError):
        return JsonResponse({"error": "Card setup is unavailable for this booking."}, status=404)
