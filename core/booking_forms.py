import uuid
from decimal import Decimal

from django import forms
from django.utils import timezone

from .models import Booking, Customer, PricingPolicy, Session


class CustomerChoice(forms.ModelChoiceField):
    def label_from_instance(self, customer):
        return f"{customer.customer_number} · {customer.last_name} · {customer.phone}"


class TestBookingForm(forms.Form):
    customer = CustomerChoice(queryset=Customer.objects.order_by("last_name", "pk"))
    session = forms.ModelChoiceField(queryset=Session.objects.none())
    children = forms.IntegerField(
        min_value=0, max_value=32767, initial=1, label="Children ages 1–11"
    )
    adults = forms.IntegerField(min_value=0, max_value=32767, initial=1, label="Adults ages 12+")
    babies = forms.IntegerField(min_value=0, max_value=32767, initial=0, label="Babies under one")
    socks = forms.IntegerField(min_value=0, max_value=2147483647, initial=0, label="Grip socks")
    supervised = forms.BooleanField(required=False, label="Supervised drop-off play")
    expected_method = forms.ChoiceField(
        choices=Booking._meta.get_field("expected_method").choices, label="Expected payment method"
    )
    override_capacity = forms.BooleanField(required=False, label="Owner: override session capacity")
    creation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput, required=False)

    def __init__(self, *args, owner=False, booking=None, customer=None, **kwargs):
        initial = {}
        if customer:
            initial["customer"] = customer
        if booking:
            initial = {
                field: getattr(booking, field)
                for field in ("children", "adults", "babies", "socks", "expected_method")
            }
            initial["version"] = booking.edit_version
        super().__init__(*args, initial=initial, **kwargs)
        self.fields["session"].queryset = Session.objects.filter(
            ends_at__gt=timezone.now(), closed=False, kind=Session.Kind.ORDINARY
        )
        if not owner:
            self.fields.pop("override_capacity")
        if booking:
            for field in ("customer", "session", "supervised", "creation_key"):
                self.fields.pop(field)
            self.fields["version"].required = True
        else:
            self.fields.pop("version")


class TimingForm(forms.Form):
    session = forms.ModelChoiceField(queryset=Session.objects.none())
    version = forms.IntegerField(widget=forms.HiddenInput, min_value=1)
    override_capacity = forms.BooleanField(required=False, label="Owner: override session capacity")

    def __init__(self, *args, booking, owner=False, **kwargs):
        super().__init__(
            *args,
            initial={"session": booking.session_id, "version": booking.edit_version},
            **kwargs,
        )
        self.fields["session"].queryset = Session.objects.filter(
            ends_at__gt=timezone.now(), closed=False, kind=Session.Kind.ORDINARY
        )
        if not owner:
            self.fields.pop("override_capacity")


class PricingPolicyForm(forms.ModelForm):
    tax_percent = forms.DecimalField(
        min_value=0, max_value=100, decimal_places=2, label="Staging sales tax (%)"
    )
    fee_percent = forms.DecimalField(
        min_value=0, max_value=100, decimal_places=2, label="Card processing fee (%)"
    )

    class Meta:
        model = PricingPolicy
        fields = (
            "child_price",
            "extra_adult_price",
            "minimum_admission",
            "supervised_price",
            "sock_price",
        )

    def __init__(self, *args, policy=None, **kwargs):
        initial = {name: getattr(policy, name) for name in self.Meta.fields} if policy else {}
        if policy:
            initial.update(
                tax_percent=policy.tax_rate * 100, fee_percent=policy.card_fee_rate * 100
            )
        # Never bind an existing immutable policy as this ModelForm's instance.
        super().__init__(*args, initial=initial, **kwargs)

    def clean(self):
        result = super().clean()
        if "tax_percent" in result and "fee_percent" in result:
            self.instance.tax_rate = result["tax_percent"] / Decimal(100)
            self.instance.card_fee_rate = result["fee_percent"] / Decimal(100)
        return result
