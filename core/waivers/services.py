"""Explicit signatures, current coverage, share-link privacy and evidence retention."""

import hashlib
import secrets
import uuid
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.template.loader import get_template, render_to_string
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from core.models import AuditEvent, Booking
from core.payments.ledger import fingerprint, lock_request
from core.payments.setup import flow_identity
from core.permissions import require_actor

from .forms import ADULT, AGREEMENT, ELECTRONIC, SignatureForm
from .models import (
    WaiverBookingLink,
    WaiverCustomerLink,
    WaiverShareLink,
    WaiverSignature,
    WaiverVersion,
)
from .storage import EvidenceStore, enabled

NY = ZoneInfo("America/New_York")
VERSION = "MD-WAIVER-2026-01"
SOURCE_HASH = "f159515b1c1c531bc57fce6a8813aa63f38f25da014459807759495f028ccdb6"


def plus_years(moment, years):
    local = moment.astimezone(NY)
    try:
        return local.replace(year=local.year + years)
    except ValueError:  # Feb 29 -> Feb 28, preserving local wall time.
        return local.replace(year=local.year + years, day=28)


@transaction.atomic
def approved_version():
    enabled()
    legal = get_template("core/waivers/legal.html").template.source
    acknowledgments = {"adult": ADULT, "agreement": AGREEMENT, "electronic": ELECTRONIC}
    content_hash = fingerprint({"legal_html": legal, "acknowledgments": acknowledgments})
    source = settings.BASE_DIR / "docs" / "waivers" / "source" / "MD Waiver (1).pdf"
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_HASH:
        raise ValidationError("The approved waiver source could not be verified.")
    version, _ = WaiverVersion.objects.get_or_create(
        code=VERSION,
        defaults={
            "legal_html": legal,
            "text_hash": content_hash,
            "source_hash": SOURCE_HASH,
            "acknowledgments": acknowledgments,
        },
    )
    if version.text_hash != content_hash or version.source_hash != SOURCE_HASH:
        raise ValidationError("Waiver text changed without a new approved version.")
    return version


def share_expiration(booking):
    day = timezone.localtime(booking.session.starts_at, NY).date() + timedelta(days=1)
    return datetime.combine(day, time.max, tzinfo=NY)


def share_for_token(token):
    enabled()
    if not isinstance(token, str) or len(token) > 100:
        raise ValidationError("This waiver link is unavailable.")
    digest = hashlib.sha256(token.encode()).hexdigest()
    try:
        link = WaiverShareLink.objects.select_related("booking__session").get(
            token_hash=digest, revoked_at__isnull=True
        )
    except WaiverShareLink.DoesNotExist:
        raise ValidationError("This waiver link is unavailable.") from None
    if timezone.now() > share_expiration(link.booking):
        raise ValidationError("this link has expired, since you've already had your appointment.")
    if link.booking.attendance == "cancelled":
        raise ValidationError(
            "This waiver link is unavailable. Please contact MonkeyDo for assistance."
        )
    return link


@transaction.atomic
def create_share(*, actor, booking_id):
    enabled()
    require_actor(actor, "core.change_booking")
    require_actor(actor, "core.view_booking")
    booking = Booking.objects.get(pk=booking_id, workflow="integrated_v1")
    token = secrets.token_urlsafe(32)
    link = WaiverShareLink.objects.create(
        booking=booking, token_hash=hashlib.sha256(token.encode()).hexdigest(), actor=actor
    )
    AuditEvent.objects.create(
        actor=actor,
        action="waiver.share_created",
        record_type="booking",
        record_id=str(booking.pk),
        changes={"link_id": str(link.pk)},
    )
    return link, token


def signing_context(*, flow=None, share_token=None):
    if (flow is None) == (share_token is None):
        raise ValidationError("Use the current booking or its secure waiver link.")
    if share_token is not None:
        share = share_for_token(share_token)
        return hashlib.sha256(("shared:" + str(share.pk)).encode()).hexdigest(), share.booking, None
    digest, customer = flow_identity(flow)
    return digest, None, customer


def evidence_bytes(signature):
    return render_to_string(
        "core/waivers/evidence.html",
        {
            "signature": signature,
            "legal_html": signature.version.legal_html,
            "signed_iso": signature.signed_at.astimezone(NY).isoformat(),
            "valid_iso": signature.valid_until.astimezone(NY).isoformat(),
            "adult_text": signature.version.acknowledgments["adult"],
            "agreement_text": signature.version.acknowledgments["agreement"],
            "electronic_text": signature.version.acknowledgments["electronic"],
        },
    ).encode("utf-8")


@transaction.atomic
def prepare_signature(*, data, flow=None, share_token=None, ip=None, user_agent=""):
    enabled()
    form = SignatureForm(data)
    if not form.is_valid():
        raise ValidationError(form.errors.as_data())
    values = form.cleaned_data
    version = approved_version()
    if values["version"] != version.pk or values["text_hash"] != version.text_hash:
        raise ValidationError("The waiver changed. Read and sign the current version.")
    digest, booking, customer = signing_context(flow=flow, share_token=share_token)
    key = lock_request(values["request_key"])
    facts = {
        k: values[k]
        for k in (
            "signer_name",
            "signer_email",
            "signer_phone",
            "relationship",
            "minors",
            "adult_accepted",
            "waiver_accepted",
            "electronic_accepted",
        )
    }
    identity = fingerprint(
        facts | {"flow": digest, "version": version.pk, "text_hash": version.text_hash}
    )
    previous = WaiverSignature.objects.filter(request_key=key).first()
    if previous:
        if previous.fingerprint != identity:
            raise ValidationError(
                "This signing request has already been used for different details."
            )
        return previous, booking, customer
    when = timezone.now()
    candidate = WaiverSignature(
        request_key=key,
        fingerprint=identity,
        version=version,
        flow_hash=digest,
        signed_at=when,
        valid_until=plus_years(when, 1),
        delete_after=plus_years(when, 2),
        object_key="staging/waivers/" + uuid.uuid4().hex + ".html",
        ip_address=ip,
        user_agent=user_agent[:512],
        **facts,
    )
    candidate.evidence_hash = hashlib.sha256(evidence_bytes(candidate)).hexdigest()
    candidate.full_clean()
    candidate.save()
    # Preserve intended associations even if the object write/acknowledgment fails.
    # Pending evidence never qualifies as valid coverage.
    if booking:
        WaiverBookingLink.objects.get_or_create(signature=candidate, booking=booking)
    if customer:
        WaiverCustomerLink.objects.get_or_create(signature=candidate, customer=customer)
    return candidate, booking, customer


@transaction.atomic
def complete_signature(signature_id, *, booking=None, customer=None):
    signature = WaiverSignature.objects.select_for_update().get(pk=signature_id)
    if signature.state not in {"pending", "signed"} or signature.delete_after <= timezone.now():
        raise ValidationError("This evidence is no longer available for signing.")
    first = signature.state == "pending"
    if first:
        signature.state = "signed"
        signature.save(update_fields=["state"])
        AuditEvent.objects.create(
            actor=None,
            action="waiver.signed",
            record_type="waiver",
            record_id=str(signature.pk),
            changes={"version": signature.version_id, "evidence_hash": signature.evidence_hash},
        )
    if customer is not None:
        WaiverCustomerLink.objects.get_or_create(signature=signature, customer=customer)
    if booking is not None:
        WaiverBookingLink.objects.get_or_create(signature=signature, booking=booking)
    if first and settings.BOOKING_EMAIL_ENABLED:
        for linked in signature.booking_links.select_related(
            "booking__customer", "booking__session"
        ):
            booking = linked.booking
            if not booking.customer.email:
                continue
            from core.communications.content import waiver_completed
            from core.communications.services import enqueue

            enqueue(
                key=f"waiver-completed:{signature.pk}:{booking.pk}",
                kind="waiver_completed",
                recipient=booking.customer.email,
                subject="A waiver was completed for your MonkeyDo visit",
                text=waiver_completed(signature, booking),
                customer=booking.customer,
                booking=booking,
            )
    return signature


def reconcile_evidence(*, actor, signature_id):
    enabled()
    require_actor(actor, "core.view_signed_waiver", owner=True)
    signature = WaiverSignature.objects.get(
        pk=signature_id, state="pending", delete_after__gt=timezone.now()
    )
    EvidenceStore().get(signature.object_key, signature.evidence_hash)
    result = complete_signature(signature.pk)
    AuditEvent.objects.create(
        actor=actor,
        action="waiver.storage_reconciled",
        record_type="waiver",
        record_id=str(signature.pk),
    )
    return result


@sensitive_variables()
def sign(*, data, flow=None, share_token=None, ip=None, user_agent=""):
    signature, booking, customer = prepare_signature(
        data=data, flow=flow, share_token=share_token, ip=ip, user_agent=user_agent
    )
    if signature.state == "signed":
        return signature
    if signature.state != "pending":
        raise ValidationError("This signature is no longer available.")
    payload = evidence_bytes(signature)
    EvidenceStore().put(signature.object_key, payload, signature.evidence_hash)
    return complete_signature(signature.pk, booking=booking, customer=customer)


def valid_customer_signatures(customer, *, at=None):
    return WaiverSignature.objects.filter(
        customer_links__customer=customer,
        state="signed",
        version_id=VERSION,
        signed_at__lte=timezone.now(),
        valid_until__gt=at or timezone.now(),
    ).order_by("-signed_at")


@transaction.atomic
def bind_booking(*, flow, booking):
    digest, customer = flow_identity(flow)
    if customer is not None and customer.pk != booking.customer_id:
        raise ValidationError("The waiver customer does not match this booking.")
    ids = flow.get("waiver_signatures", [])
    if (
        not isinstance(ids, list)
        or len(ids) > 100
        or not ids
        or flow.get("waiver_coverage") is not True
    ):
        raise ValidationError("Complete waiver coverage before confirming this booking.")
    for signature_id in ids:
        signature = WaiverSignature.objects.get(
            pk=signature_id,
            state="signed",
            version_id=VERSION,
            valid_until__gt=booking.session.starts_at,
        )
        if signature.flow_hash != digest and not (
            customer and signature.customer_links.filter(customer=customer).exists()
        ):
            raise ValidationError("This waiver does not belong to the verified customer.")
        WaiverBookingLink.objects.get_or_create(signature=signature, booking=booking)
        if signature.flow_hash == digest:
            WaiverCustomerLink.objects.get_or_create(signature=signature, customer=booking.customer)
    from .models import BookingWaiverReview

    BookingWaiverReview.objects.get_or_create(
        booking=booking,
        defaults={
            "coverage_confirmed": True,
            "share_requested": bool(flow.get("waiver_share_requested")),
        },
    )


def signed_evidence(*, actor, signature_id):
    enabled()
    require_actor(actor, "core.view_signed_waiver")
    require_actor(actor, "core.view_customer")
    signature = WaiverSignature.objects.get(
        pk=signature_id, state="signed", delete_after__gt=timezone.now()
    )
    data = EvidenceStore().get(signature.object_key, signature.evidence_hash)
    AuditEvent.objects.create(
        actor=actor,
        action="waiver.evidence_viewed",
        record_type="waiver",
        record_id=str(signature.pk),
    )
    return data


def expire_evidence(*, limit=100):
    enabled()
    if not 1 <= limit <= 100:
        raise ValidationError("Use a bounded retention batch.")
    store = EvidenceStore()
    ids = list(
        WaiverSignature.objects.filter(
            delete_after__lte=timezone.now(), state__in=["pending", "signed", "deleting"]
        ).values_list("pk", flat=True)[:limit]
    )
    removed = 0
    for pk in ids:
        with transaction.atomic():
            signature = WaiverSignature.objects.select_for_update().get(pk=pk)
            if signature.state == "deleted":
                continue
            signature.state = "deleting"
            signature.save(update_fields=["state"])
        store.delete(signature.object_key)  # Idempotent; metadata is retained if this fails.
        with transaction.atomic():
            signature = WaiverSignature.objects.select_for_update().get(pk=pk)
            signature.state = "deleted"
            signature.deleted_at = timezone.now()
            signature.signer_email = signature.signer_phone = signature.user_agent = ""
            signature.ip_address = None
            signature.save(
                update_fields=[
                    "state",
                    "deleted_at",
                    "signer_email",
                    "signer_phone",
                    "ip_address",
                    "user_agent",
                ]
            )
            AuditEvent.objects.create(
                actor=None,
                action="waiver.evidence_removed",
                record_type="waiver",
                record_id=str(pk),
            )
            removed += 1
    return removed


def booking_coverage(booking):
    from .models import BookingWaiverReview

    review = BookingWaiverReview.objects.filter(booking=booking).first()
    if review and review.paper_signed:
        return True
    return bool(
        review
        and review.coverage_confirmed
        and booking.waiver_links.filter(
            signature__state="signed",
            signature__signed_at__lte=timezone.now(),
            signature__valid_until__gt=booking.session.starts_at,
        ).exists()
    )


@transaction.atomic
def set_paper(*, actor, booking_id, revision, signed):
    from .models import BookingWaiverReview

    enabled()
    for permission in ("core.view_booking", "core.change_booking", "core.view_waiversignature"):
        require_actor(actor, permission)
    if type(signed) is not bool or type(revision) is not int or revision < 0:
        raise ValidationError("Review the current paper-waiver form.")
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    if booking.workflow != "integrated_v1":
        raise ValidationError(
            "Use a new integrated booking; earlier test records are preserved unchanged."
        )
    review = BookingWaiverReview.objects.select_for_update().filter(booking=booking).first()
    if revision != (review.revision if review else 0):
        raise ValidationError("Waiver coverage changed. Reload the booking before saving.")
    before = review.paper_signed if review else False
    if review is None:
        review = BookingWaiverReview(booking=booking)
    else:
        review.revision += 1
    review.paper_signed = signed
    if not signed:
        review.coverage_confirmed = False
    review.save()
    AuditEvent.objects.create(
        actor=actor,
        action="waiver.paper_reviewed",
        record_type="booking",
        record_id=str(booking.reference),
        changes={"paper_waivers_signed": {"before": before, "after": signed}},
    )
    return review
