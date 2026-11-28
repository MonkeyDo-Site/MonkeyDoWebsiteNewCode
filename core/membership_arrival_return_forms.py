"""A completed manual return is recorded on the existing pending-arrival page."""

import json
import uuid
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .membership_arrival_receipts import rows
from .membership_arrival_returns import record, review
from .payments.receipts import receipt_date


class PendingVisitReturnForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    reviewed_sources = forms.CharField(max_length=2000, widget=forms.HiddenInput)
    receipt = forms.ChoiceField(label="Original visit payment")
    amount = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01"), label="Amount already returned"
    )
    completed_on = forms.DateField(
        label="Actual return date",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    verified_returned = forms.BooleanField(
        label="I returned this amount using the original payment method."
    )

    def __init__(self, *args, intent, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.intent, self.actor = intent, actor
        for name, field in self.fields.items():
            field.widget.attrs["id"] = "id_return_" + name
        sources = rows(intent)
        names = {"cash": "Cash", "check": "Check", "zelle": "Zelle", "gift_card": "Gift card"}
        self.fields["receipt"].choices = [
            (str(r.pk), f"{names[r.tender]} · ${r.available_amount:.2f} unused") for r in sources
        ]
        fingerprints = {}
        for source in sources:
            try:
                fingerprints[str(source.pk)] = review(actor=actor, receipt_id=source.pk)[
                    "fingerprint"
                ]
            except ValidationError:
                pass
        self.initial.update(
            request_key=uuid.uuid4(),
            reviewed_sources=json.dumps(fingerprints),
            completed_on=receipt_date(),
        )
        self.initial["receipt"] = next(iter(fingerprints), "")

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        try:
            fingerprints = json.loads(data["reviewed_sources"])
            data["receipt_id"] = uuid.UUID(data["receipt"])
            data["reviewed_hash"] = fingerprints[data["receipt"]]
            if not isinstance(data["reviewed_hash"], str) or len(data["reviewed_hash"]) != 64:
                raise ValueError
        except (ValueError, TypeError, KeyError):
            raise ValidationError(
                "The receipt balance changed. Reopen this page and review the unused funds."
            ) from None
        data["completed_on"] = receipt_date(data["completed_on"])
        return data

    def save(self):
        data = self.cleaned_data
        return record(
            actor=self.actor,
            receipt_id=data["receipt_id"],
            request_key=data["request_key"],
            value=data["amount"],
            completed_on=data["completed_on"],
            reviewed_hash=data["reviewed_hash"],
            confirmed=True,
            verified_returned=data["verified_returned"],
        )
