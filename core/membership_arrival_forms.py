"""Membership controls live on arrival, with the same reviewed final action."""

import copy
import uuid

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q

from .availability import NEW_YORK
from .models import PaymentMethod


class SavedCard(forms.ModelChoiceField):
    def to_python(self, value):
        return None if value == "new" else super().to_python(value)

    def label_from_instance(self, obj):
        return f"{obj.brand or 'Card'} ending in {obj.last_four}"


def configure(form, booking, actor):
    if (
        not settings.MEMBERSHIP_SALES_ENABLED
        or actor is None
        or not actor.has_perms(
            ["core.view_membershippurchase", "core.add_membershippurchase", "core.collect_payment"]
        )
    ):
        return
    available = Q(reusable=True)
    values = form.data if form.is_bound else form.initial
    form.arrival_card_authority = None
    if values.get("member_card_authorization"):
        from .membership_card_setup import source
        from .membership_records import MembershipCardAuthorization

        try:
            authority = MembershipCardAuthorization.objects.get(
                pk=values["member_card_authorization"],
                actor=actor,
                customer=booking.customer,
                request_key=purchase_key(values.get("request_key")),
            )
            selected = source(authority)
            if selected.customer_id == booking.customer_id:
                available |= Q(pk=selected.pk)
                form.arrival_card_authority = authority
        except (MembershipCardAuthorization.DoesNotExist, ValidationError, ValueError, TypeError):
            pass
    fields = {
        "member_card_authorization": forms.UUIDField(required=False, widget=forms.HiddenInput),
        "member_add": forms.BooleanField(required=False, label="Buy a membership with this visit"),
        "member_kind": forms.ChoiceField(
            required=False,
            choices=[("subscription", "Subscription"), ("unlimited", "Unlimited")],
            initial="subscription",
            label="Membership",
        ),
        "member_places": forms.IntegerField(
            required=False, min_value=1, max_value=32767, initial=1, label="Membership places"
        ),
        "member_months": forms.IntegerField(
            required=False,
            min_value=1 if actor.is_superuser else 3,
            max_value=1200,
            initial=3,
            label="Months",
        ),
        "member_billing": forms.ChoiceField(
            required=False,
            choices=[("monthly", "Monthly installments"), ("prepaid", "Pay full term now")],
            initial="monthly",
            label="Membership payment",
        ),
        "member_starts_on": forms.DateField(
            required=False,
            initial=booking.session.starts_at.astimezone(NEW_YORK).date(),
            widget=forms.DateInput(attrs={"type": "date"}),
            label="Membership begins",
        ),
        "member_card": SavedCard(
            required=False,
            queryset=PaymentMethod.objects.filter(
                available,
                customer=booking.customer,
                state="active",
                environment="sandbox",
                provider_method__isnull=False,
            ),
            label="Card for membership payment and scheduled installments",
            empty_label="Choose a saved card",
        ),
        "member_credit": forms.DecimalField(
            required=False,
            min_value=0,
            max_digits=14,
            decimal_places=2,
            initial=0,
            label="Existing customer credit to apply",
        ),
        "member_accepted": forms.BooleanField(
            required=False,
            label="The customer accepts these membership terms and the scheduled card payments shown.",
        ),
        "member_received": forms.BooleanField(
            required=False, label="The combined cash or check amount shown was actually received."
        ),
    }
    if actor.is_superuser:
        fields.update(
            member_minimum_override=forms.BooleanField(
                required=False, label="Owner: approve a shorter initial membership term"
            ),
            member_comped=forms.BooleanField(
                required=False, label="Owner: complimentary membership"
            ),
            member_send_confirmation=forms.ChoiceField(
                required=False,
                choices=[("", "Choose Yes or No"), ("yes", "Yes"), ("no", "No")],
                label="Send combined confirmation for complimentary membership?",
            ),
        )
    form.fields.update(fields)
    form.fields["member_received"].arrival_hidden = values.get("method") in {"card", "gift_card"}
    if values.get("member_add") and values.get("method") == "gift_card":
        form.fields[
            "gift_card_verified"
        ].label = (
            "The physical gift card has been presented and verified for the combined amount shown."
        )
    if values.get("member_card") == "new":
        form.fields["member_card"].widget.choices = [
            *form.fields["member_card"].choices,
            ("new", "Enter a new card"),
        ]


def clean(form):
    data = form.cleaned_data
    if not data.get("member_add"):
        return
    data["member_card_new"] = form.data.get("member_card") == "new"
    for name in ("kind", "places", "months", "billing", "starts_on"):
        if not data.get("member_" + name):
            form.add_error("member_" + name, "Complete this membership choice.")
    if form.previewing:
        return
    if not data.get("member_accepted"):
        form.add_error("member_accepted", "The customer must accept the reviewed membership terms.")


def selection(data):
    return {
        **{
            name: data["member_" + name]
            for name in ("kind", "places", "months", "billing", "starts_on")
        },
        "minimum_override": data.get("member_minimum_override", False),
        "comped": data.get("member_comped", False),
        "credit_amount": data.get("member_credit") or 0,
    }


def preview(*, actor, booking_id, kind, data, validate_waivers=True, pending_intent=None):
    from . import membership_arrival
    from .payments import checkout

    if pending_intent:
        from . import membership_arrival_recovery

        return membership_arrival_recovery.preview(
            actor=actor, intent=pending_intent, data=data, validate_waivers=validate_waivers
        )
    if kind != "arrival" or not data.get("member_add"):
        return checkout.preview(
            actor=actor,
            booking_id=booking_id,
            kind=kind,
            data=data,
            validate_waivers=validate_waivers,
        ), None
    member = data.get("member_card")
    reviewed = membership_arrival.review(
        actor=actor,
        booking_id=booking_id,
        data=data,
        selection=selection(data),
        method_id=member.pk if member else None,
        card_authorization_id=data.get("member_card_authorization"),
        validate_waivers=validate_waivers,
    )
    return (
        None,
        None,
        reviewed["quote"],
        reviewed["plan"],
        None,
        reviewed["fingerprint"],
    ), reviewed


def ready(data, combined):
    if combined is None:
        return True
    return bool(
        data.get("member_accepted")
        and (
            combined["offer"]["expected_method"] == "card"
            or (
                combined["offer"]["expected_method"] == "gift_card"
                and data.get("gift_card_verified")
            )
            or data.get("member_received")
            or combined["facts"]["received_today"] == "0.00"
        )
        and (
            combined["offer"]["comped"]
            or (
                combined["offer"]["billing"] != "monthly"
                and not (
                    combined["offer"]["expected_method"] == "card"
                    and combined["facts"]["membership_due"] != "0.00"
                )
            )
            or data.get("member_card")
            or data.get("member_card_new")
        )
        and (
            not combined["offer"]["comped"] or data.get("member_send_confirmation") in {"yes", "no"}
        )
    )


def confirm(
    *, actor, booking_id, kind, data, request_key, reviewed_hash, confirmed, pending_intent=None
):
    from . import membership_arrival
    from .payments import checkout

    if pending_intent:
        from . import membership_arrival_recovery

        return membership_arrival_recovery.confirm(
            actor=actor,
            intent_id=pending_intent.pk,
            data=data,
            request_key=request_key,
            reviewed_hash=reviewed_hash,
            confirmed=confirmed,
        )
    if kind != "arrival" or not data.get("member_add"):
        return checkout.confirm(
            actor=actor,
            booking_id=booking_id,
            kind=kind,
            data=data,
            request_key=request_key,
            reviewed_hash=reviewed_hash,
            confirmed=confirmed,
        )
    member = data.get("member_card")
    record = membership_arrival.confirm(
        actor=actor,
        booking_id=booking_id,
        data=data,
        selection=selection(data),
        method_id=member.pk if member else None,
        card_authorization_id=data.get("member_card_authorization"),
        request_key=request_key,
        reviewed_hash=reviewed_hash,
        confirmed=confirmed,
        accepted=data.get("member_accepted", False),
        verified_received=data.get("member_received", False),
        send_confirmation={"yes": True, "no": False}.get(data.get("member_send_confirmation")),
    )
    from .membership_records import MembershipArrivalIntent

    return record if isinstance(record, MembershipArrivalIntent) else record.checkout


def purchase_key(arrival_key):
    return uuid.uuid5(uuid.UUID(str(arrival_key)), "membership")


def card_purchase(booking, data, combined):
    if not combined or combined["offer"]["comped"]:
        return None
    offer = combined["offer"]
    return dict(
        operation="purchase",
        prior_id="",
        customer=booking.customer_id,
        **{name: data["member_" + name] for name in ("kind", "places", "months", "billing")},
        starts_on=data["member_starts_on"].isoformat(),
        expected_method=data["method"],
        credit_amount=str(data.get("member_credit") or 0),
        minimum_override=data.get("member_minimum_override", False),
        comped=False,
        request_key=str(purchase_key(data["request_key"])),
        reviewed=offer["fingerprint"],
    )


def card_review(combined):
    from .payments.ledger import fingerprint

    if not combined:
        return ""
    facts = copy.deepcopy(combined["facts"])
    for name in ("method_id", "card_authorization_id", "membership_card_last_four"):
        facts.pop(name, None)
    return fingerprint(facts)
