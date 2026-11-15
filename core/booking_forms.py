import uuid
from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import Booking, CalendarDate, Customer, PricingPolicy, Session


class CustomerChoice(forms.ModelChoiceField):
    def label_from_instance(self, customer):
        return f"{customer.customer_number} · {customer.last_name} · {customer.phone}"


class TestBookingForm(forms.Form):
    payment_reviewed = forms.ChoiceField(
        required=False,
        label="If the amount changes, would you like to change the expected payment method?",
        choices=[
            ("", "Choose when the amount changes"),
            ("keep", "No — keep the current method"),
            ("change", "Yes — use the method selected below"),
        ],
    )
    customer = CustomerChoice(queryset=Customer.objects.order_by("last_name", "pk"))
    session = forms.ModelChoiceField(queryset=Session.objects.none())
    children = forms.IntegerField(
        min_value=0, max_value=32767, initial=1, label="Children ages 1–11"
    )
    adults = forms.IntegerField(min_value=0, max_value=32767, initial=1, label="Adults ages 12+")
    babies = forms.IntegerField(min_value=0, max_value=32767, initial=0, label="Babies under one")
    socks = forms.IntegerField(min_value=0, max_value=2147483647, initial=0, label="Grip socks")
    referral_source = forms.CharField(max_length=240, required=False, label="Referral source")
    supervised = forms.BooleanField(required=False, label="Supervised Play")
    expected_method = forms.ChoiceField(
        choices=Booking._meta.get_field("expected_method").choices, label="Expected payment method"
    )
    override_capacity = forms.BooleanField(required=False, label="Owner: override session capacity")
    creation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput, required=False)

    def __init__(self, *args, owner=False, booking=None, customer=None, **kwargs):
        self.booking = booking
        initial = {}
        if customer:
            initial["customer"] = customer
        if booking:
            initial = {
                field: getattr(booking, field)
                for field in (
                    "children",
                    "adults",
                    "babies",
                    "socks",
                    "expected_method",
                    "supervised",
                    "referral_source",
                    "session",
                )
            }
            initial["version"] = booking.edit_version
        super().__init__(*args, initial=initial, **kwargs)
        self.fields["session"].queryset = Session.objects.filter(
            Q(source_slot__isnull=True)
            | Q(source_slot__active=True, source_slot__archived_at__isnull=True),
            ends_at__gt=timezone.now(),
            closed=False,
            kind=Session.Kind.ORDINARY,
        ).exclude(starts_at__date__in=CalendarDate.objects.filter(closed=True).values("day"))
        if not owner:
            self.fields.pop("override_capacity")
        if booking:
            for field in ("customer", "creation_key"):
                self.fields.pop(field)
            self.fields["version"].required = True
        else:
            self.fields.pop("version")
            self.fields.pop("payment_reviewed")
        customer_picker(self)

    def clean(self):
        from .pricing import booking_quote

        data = super().clean()
        if self.booking and not self.errors:
            old = self.booking.quotes.first()
            if data.get("payment_reviewed") == "keep":
                data["expected_method"] = self.booking.expected_method
            if old:
                quote = booking_quote(
                    old.policy,
                    **{
                        k: data[k]
                        for k in (
                            "children",
                            "adults",
                            "babies",
                            "socks",
                            "supervised",
                            "expected_method",
                        )
                    },
                )
                if quote["total"] != old.snapshot["total"] and not data.get("payment_reviewed"):
                    self.add_error(
                        "payment_reviewed",
                        f"The revised estimate is ${quote['total']} (previously ${old.snapshot['total']}). Choose whether to keep or change the expected payment method. No payment will be processed.",
                    )
        return data


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
            Q(source_slot__isnull=True)
            | Q(source_slot__active=True, source_slot__archived_at__isnull=True),
            ends_at__gt=timezone.now(),
            closed=False,
            kind=Session.Kind.ORDINARY,
        ).exclude(starts_at__date__in=CalendarDate.objects.filter(closed=True).values("day"))
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


def customer_picker(form):
    """Render only the selected record; authorized async search supplies choices."""
    field = form.fields.get("customer")
    if field is None:
        return
    selected = form.data.get("customer") if form.is_bound else form.initial.get("customer")
    if isinstance(selected, Customer):
        selected = selected.pk
    row = (
        Customer.objects.filter(pk=selected).first()
        if str(selected).isdigit() and len(str(selected)) < 19
        else None
    )
    field.widget.choices = [("", "Search and select a customer")] + (
        [(row.pk, field.label_from_instance(row))] if row else []
    )
    field.widget.attrs["data-customer-picker"] = "true"
