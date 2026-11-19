"""Signed, bounded, deduplicated Banquest events; reconcile money with the API."""

import hashlib
import hmac
import json
import re
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .amounts import amount
from .gateway import ProviderFailure, reference
from .jobs import enqueue
from .ledger import enabled
from .models import PaymentOperation, ProviderEvent


@transaction.atomic
def receive(body, signature):
    enabled()
    key = settings.BANQUEST_WEBHOOK_KEY
    if (
        not key
        or len(body) > 65536
        or not isinstance(signature, str)
        or not re.fullmatch("[0-9a-fA-F]{64}", signature)
    ):
        raise ValidationError("Invalid provider notification.")
    digest = hmac.new(key.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, signature.lower()):
        raise ValidationError("Invalid provider notification.")
    try:
        data = json.loads(body, parse_float=Decimal)
        event_id = data["id"]
        event_type = data["event"] + "." + data["type"]
        when = parse_datetime(data["timestamp"])
        if (
            not isinstance(event_id, str)
            or not 1 <= len(event_id) <= 200
            or len(event_type) > 80
            or when is None
            or timezone.is_naive(when)
        ):
            raise ValueError
        # Ignore unrelated event classes without storing arbitrary customer data.
        facts = {}
        provider_id = ""
        if data["event"] == "transaction":
            payload = data.get("data", {})
            txn = payload.get("transaction", payload)
            raw_id = payload.get("reference_number", txn.get("id"))
            if raw_id is not None:
                provider_id = reference(raw_id)
            operation_key = txn.get("custom_fields", {}).get("custom1")
            if operation_key:
                facts["operation"] = str(uuid.UUID(operation_key))
            if "amount" in txn.get("amount_details", {}):
                facts["amount"] = str(amount(txn["amount_details"]["amount"]))
        hashed = hashlib.sha256(body).hexdigest()
        event, created = ProviderEvent.objects.get_or_create(
            event_id=event_id,
            defaults={
                "event_type": event_type,
                "payload_hash": hashed,
                "provider_reference": provider_id,
                "occurred_at": when,
                "facts": facts,
            },
        )
        if not created and event.payload_hash != hashed:
            raise ValidationError("Conflicting provider notification.")
        enqueue(kind="provider_event", reference=event.pk, key="provider-event:" + event_id)
        return event
    except (KeyError, ValueError, TypeError, AttributeError, ProviderFailure):
        raise ValidationError("Invalid provider notification.") from None


def process_event(event_id):
    event = ProviderEvent.objects.get(pk=event_id)
    if not event.event_type.startswith("transaction."):
        return
    from .operations import reconcile

    operation_id = event.facts.get("operation")
    if operation_id:
        operation = PaymentOperation.objects.filter(pk=operation_id, tender="card").first()
    else:
        # Status events may not carry metadata; never choose arbitrarily when
        # a reference is shared by a receipt and its subsequent void.
        candidates = (
            list(
                PaymentOperation.objects.filter(
                    provider_reference=event.provider_reference, tender="card"
                ).exclude(state__in=["ready", "succeeded", "declined"])[:2]
            )
            if event.provider_reference
            else []
        )
        operation = candidates[0] if len(candidates) == 1 else None
    if operation is None or operation.state in {"ready", "succeeded", "declined"}:
        return
    # Signed payloads only trigger read-only reconciliation. They do not bypass
    # immutable amount/identity checks or directly post a financial result.
    if event.provider_reference and operation.provider_reference == event.provider_reference:
        reconcile(operation_id=operation.pk)
    elif event.provider_reference and not operation.provider_reference and operation_id:
        from .gateway import Gateway
        from .ledger import record_result
        from .operations import verify_transaction

        data = Gateway().transaction(event.provider_reference)
        verified = verify_transaction(operation, data)
        record_result(
            operation_id=operation.pk,
            state="succeeded",
            source="webhook",
            provider_reference=verified,
            code="captured",
            occurred_at=event.occurred_at,
        )


@csrf_exempt
@require_POST
def endpoint(request):
    if not settings.PAYMENT_SANDBOX_ENABLED or not settings.BANQUEST_WEBHOOK_KEY:
        return HttpResponse(status=404)
    try:
        if int(request.META.get("CONTENT_LENGTH") or 0) > 65536:
            return HttpResponse(status=413)
        receive(request.body, request.headers.get("X-Signature", ""))
    except (ValidationError, ValueError):
        return HttpResponse(status=400)
    return HttpResponse(status=202)
