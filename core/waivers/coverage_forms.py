from django import forms
from django.db.models import Q

from core.payments.setup import flow_identity
from core.public_booking import public_session

from .models import WaiverSignature
from .services import VERSION


class WaiverChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, signature):
        covered = ", ".join(signature.minors) or "Self only"
        return f"{signature.signer_name} — {covered}"


class CoverageForm(forms.Form):
    signatures = WaiverChoiceField(
        queryset=WaiverSignature.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Waivers covering this visit",
    )
    additional_minors = forms.ChoiceField(
        choices=[
            ("no", "No — all minors attending are listed on these waivers"),
            ("yes", "Yes — additional minors need a waiver"),
        ],
        widget=forms.RadioSelect,
        label="Are any additional minors attending who are not on these waivers?",
    )
    coverage_confirmed = forms.BooleanField(
        label="I confirm that everyone in this booking has the required waiver coverage."
    )

    def __init__(self, *args, flow, **kwargs):
        super().__init__(*args, **kwargs)
        self.minimum_minors = flow["details"]["children"] + flow["details"]["babies"]
        digest, customer = flow_identity(flow)
        scope = Q(flow_hash=digest)
        if customer:
            scope |= Q(customer_links__customer=customer)
        session = public_session(flow["session_id"])
        self.fields["signatures"].queryset = (
            WaiverSignature.objects.filter(
                scope, state="signed", version_id=VERSION, valid_until__gt=session.starts_at
            )
            .distinct()
            .order_by("-signed_at")
        )
        self.fields["signatures"].initial = flow.get("waiver_signatures", [])

    def clean(self):
        data = super().clean()
        if data.get("additional_minors") == "yes":
            raise forms.ValidationError(
                "Please sign a waiver for the additional minors before continuing."
            )
        selected = data.get("signatures")
        if selected is not None:
            names = {name.strip().casefold() for signature in selected for name in signature.minors}
            if len(names) < self.minimum_minors:
                raise forms.ValidationError(
                    "Please obtain waiver coverage for every child and baby in this booking before continuing."
                )
        return data
