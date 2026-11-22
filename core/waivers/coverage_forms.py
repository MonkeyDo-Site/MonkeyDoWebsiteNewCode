"""Booking-scoped coverage choices, kept separate from the actual signature."""

from django import forms
from django.db.models import Q
from django.utils import timezone

from core.payments.setup import flow_identity
from core.public_booking import public_session

from .models import WaiverSignature
from .services import COVERAGE_VERSIONS

SHARE_LABEL = (
    "I am bringing along additional minors and would like to receive the waiver link in the "
    "confirmation email for me to send to their parents to sign before the visit."
)


def available_signatures(flow):
    digest, customer = flow_identity(flow)
    scope = Q(flow_hash=digest)
    if customer:
        scope |= Q(customer_links__customer=customer)
    return WaiverSignature.objects.filter(scope, state="signed").distinct().order_by("-signed_at")


def current_signatures(flow):
    session = public_session(flow["session_id"])
    return available_signatures(flow).filter(
        version_id__in=COVERAGE_VERSIONS,
        signed_at__lte=timezone.now(),
        valid_until__gt=session.starts_at,
    )


def validate_coverage(flow, signatures, shared):
    minimum = flow["details"]["children"] + flow["details"]["babies"]
    if shared and minimum == 0:
        raise forms.ValidationError("The shared parent link is for a booking that includes minors.")
    if not signatures:
        raise forms.ValidationError("Please sign a waiver before continuing.")
    if not shared:
        names = {name.strip().casefold() for item in signatures for name in item.minors}
        if len(names) < minimum:
            raise forms.ValidationError(
                "Please sign for the remaining minors or request the parent-waiver link."
            )


class WaiverChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, signature):
        covered = ", ".join(signature.minors) or "Attending adult"
        return f"{signature.signer_name} — {covered}"


class CoverageForm(forms.Form):
    use_existing = forms.BooleanField(
        required=False, label="The previously signed waiver covers the minors in this visit."
    )
    sign_now = forms.BooleanField(
        required=False,
        label="I will sign a waiver now for all participating minors who I am responsible for.",
    )
    share_requested = forms.BooleanField(required=False, label=SHARE_LABEL)

    def __init__(self, *args, flow, **kwargs):
        super().__init__(*args, **kwargs)
        self.flow = flow
        self.signatures = list(current_signatures(flow))
        self.has_expired = (
            available_signatures(flow)
            .exclude(pk__in=[item.pk for item in self.signatures])
            .exists()
        )
        if not self.signatures:
            self.fields.pop("use_existing")
        else:
            self.fields[
                "sign_now"
            ].label = (
                "I am bringing additional minors on this visit and will sign a waiver for them now."
            )
        if self.signatures and self.has_expired:
            self.fields[
                "use_existing"
            ].label = (
                "The minors in this visit are covered under the waiver that hasn’t expired yet."
            )
            self.fields[
                "sign_now"
            ].label = "I will sign a waiver now for all participating minors who don’t have an active waiver who I am responsible for."
        self.fields["share_requested"].initial = flow.get("waiver_share_requested", False)

    def clean(self):
        data = super().clean()
        if not self.signatures and not data.get("sign_now"):
            self.add_error("sign_now", "Please select option 1 and sign your waiver.")
        if self.signatures and not (data.get("use_existing") or data.get("sign_now")):
            raise forms.ValidationError("Select existing coverage or sign a waiver now.")
        selected = self.signatures if data.get("use_existing") else []
        data["signatures"] = selected
        if not data.get("sign_now") and not self.errors:
            validate_coverage(self.flow, selected, data.get("share_requested"))
        data["coverage_confirmed"] = not data.get("share_requested")
        return data


class CoverageConfirmationForm(forms.Form):
    coverage = forms.ChoiceField(
        label="Do all minors in this booking have a current signed waiver for them?",
        choices=[
            (
                "no",
                "No — additional minors need a waiver, please send me a waiver link in my confirmation email.",
            ),
            ("yes", "Yes — all minors in this booking have a current waiver signed for them."),
        ],
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, flow, **kwargs):
        super().__init__(*args, **kwargs)
        self.flow = flow
        self.signatures = list(
            current_signatures(flow).filter(pk__in=flow.get("waiver_signatures", []))
        )
        if flow.get("waiver_share_requested"):
            self.fields["coverage"].initial = "no"

    def clean(self):
        data = super().clean()
        if data.get("coverage"):
            validate_coverage(self.flow, self.signatures, data["coverage"] == "no")
        return data
