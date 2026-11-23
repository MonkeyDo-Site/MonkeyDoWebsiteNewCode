"""Named paper records with the same customer/date boundaries as electronic coverage."""

from datetime import datetime, time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.availability import NEW_YORK
from core.models import AuditEvent, Booking
from core.payments.ledger import lock_request, writes_allowed
from core.permissions import require_actor

from .models import PaperWaiver
from .services import COVERAGE_VERSIONS, VERSION, enabled, plus_years


class SignatureList(list):
    """Small bounded union of customer-owned paper/electronic signatures."""

    def filter(self, **kwargs):
        def matches(item):
            for key, value in kwargs.items():
                if key == "pk__in":
                    if str(item.pk) not in {str(x) for x in value}:
                        return False
                elif key == "pk":
                    if str(item.pk) != str(value):
                        return False
                elif key == "version_id__in":
                    if item.version_id not in value:
                        return False
                elif key.endswith("__gt"):
                    if getattr(item, key[:-4]) <= value:
                        return False
                elif key.endswith("__lte"):
                    if getattr(item, key[:-5]) > value:
                        return False
                elif getattr(item, key) != value:
                    return False
            return True

        return SignatureList(x for x in self if matches(x))

    def exclude(self, **kwargs):
        selected = {str(x.pk) for x in self.filter(**kwargs)}
        return SignatureList(x for x in self if str(x.pk) not in selected)

    def exists(self):
        return bool(self)

    def first(self):
        return self[0] if self else None


def current_paper(customer, at=None):
    return PaperWaiver.objects.filter(
        customer=customer,
        version_code__in=COVERAGE_VERSIONS,
        signed_at__lte=timezone.now(),
        valid_until__gt=at or timezone.now(),
    ).order_by("-signed_at")


def active_customer_waivers(booking):
    from .models import WaiverSignature

    electronic = WaiverSignature.objects.filter(
        Q(customer_links__customer=booking.customer) | Q(booking_links__booking=booking),
        state="signed",
        signed_at__lte=timezone.now(),
        valid_until__gt=booking.session.starts_at,
        version_id__in=COVERAGE_VERSIONS,
    ).distinct()
    return sorted(
        [*electronic, *current_paper(booking.customer, booking.session.starts_at)],
        key=lambda x: x.signed_at,
        reverse=True,
    )


@transaction.atomic
def record(
    *,
    actor,
    booking_id,
    request_key,
    signer_name,
    relationship,
    minors,
    signed_on,
    paper_signed=False,
):
    enabled()
    writes_allowed()
    for permission in ("core.change_booking", "core.view_customer", "core.view_waiversignature"):
        require_actor(actor, permission)
    key = lock_request(request_key)
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    if booking.workflow != "integrated_v1" or paper_signed is not True:
        raise ValidationError("Confirm that the paper waiver was actually signed.")
    from .forms import SignatureForm

    form = SignatureForm(
        {
            "request_key": key,
            "version": "paper",
            "text_hash": "paper",
            "signer_name": signer_name,
            "relationship": relationship,
            "minors": "\n".join(minors) if isinstance(minors, list) else minors,
            "adult_accepted": True,
            "waiver_accepted": True,
            "electronic_accepted": True,
        }
    )
    if not form.is_valid():
        raise ValidationError(
            [str(message) for errors in form.errors.values() for message in errors]
        )
    if signed_on > timezone.localdate(timezone=NEW_YORK):
        raise ValidationError("Use the actual signing date, no later than today.")
    when = timezone.make_aware(datetime.combine(signed_on, time.min), NEW_YORK)
    values = {
        "version_code": VERSION,
        "booking_id": booking.pk,
        "customer_id": booking.customer_id,
        "signer_name": form.cleaned_data["signer_name"],
        "relationship": form.cleaned_data["relationship"],
        "minors": form.cleaned_data["minors"],
        "signed_at": when,
        "valid_until": plus_years(when, 1),
        "actor_id": actor.pk,
    }
    prior = PaperWaiver.objects.filter(request_key=key).first()
    if prior:
        if any(getattr(prior, k) != v for k, v in values.items()):
            raise ValidationError(
                "This paper record request was already used for different details."
            )
        return prior
    item = PaperWaiver.objects.create(request_key=key, **values)
    AuditEvent.objects.create(
        actor=actor,
        action="waiver.paper_recorded",
        record_type="booking",
        record_id=str(booking.reference),
        changes={"paper_waiver_id": str(item.pk), "signed_on": str(signed_on)},
    )
    return item
