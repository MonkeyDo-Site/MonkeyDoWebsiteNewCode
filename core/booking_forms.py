import uuid
from decimal import Decimal

from django import forms
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .availability import NEW_YORK
from .models import Booking, CalendarDate, Customer, PricingPolicy, Session, SessionReservationBlock


class CustomerChoice(forms.ModelChoiceField):
    def label_from_instance(self, customer):
        return f"{customer.customer_number} · {customer.last_name} · {customer.phone}"


def selectable_sessions(booking=None):
    rows = Session.objects.filter(
        Q(source_slot__isnull=True)
        | Q(source_slot__active=True, source_slot__archived_at__isnull=True),
        ends_at__gt=timezone.now(),
        closed=False,
        kind=Session.Kind.ORDINARY,
    ).exclude(starts_at__date__in=CalendarDate.objects.filter(closed=True).values("day"))
    blocks = SessionReservationBlock.objects.filter(active=True)
    if booking:
        blocks = blocks.exclude(booking=booking)
        rows = Session.objects.filter(Q(pk__in=rows.values("pk")) | Q(pk=booking.session_id))
    return rows.exclude(pk__in=blocks.values("session_id")).order_by("starts_at", "pk")


def session_date_picker(form, booking=None):
    selected = form.data.get("session") if form.is_bound else form.initial.get("session")
    if isinstance(selected, Session):
        selected = selected.pk
    current = (
        Session.objects.filter(pk=selected).first()
        if str(selected).isdigit() and len(str(selected)) < 19
        else None
    )
    day = form.data.get("session_date") if form.is_bound else None
    if not day:
        day = (
            current.starts_at.astimezone(NEW_YORK).date()
            if current
            else timezone.localdate(timezone=NEW_YORK)
        )
    try:
        day = forms.DateField().clean(day)
    except forms.ValidationError:
        form.fields["session"].queryset = Session.objects.none()
    else:
        form.initial["session_date"] = day
        form.fields["session"].queryset = selectable_sessions(booking).filter(starts_at__date=day)
    form.fields["session_date"].widget.attrs["data-session-date"] = "true"
    form.fields["session"].widget.attrs["data-dated-sessions"] = "true"


def session_capacity_summary(session, booking=None):
    from .availability import occupancy

    children, adults, supervised = occupancy(
        session, ignore_booking_id=booking.pk if booking else None
    )
    return f"Children: {max(0, session.child_capacity - children)} of {session.child_capacity} available · Total: {max(0, session.total_capacity - children - adults)} of {session.total_capacity} available · Supervised: {max(0, session.supervised_capacity - supervised)} of {session.supervised_capacity} available"


class SessionChoiceSelect(forms.Select):
    def __init__(self, *args, booking=None, **kwargs):
        self.booking = booking
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if hasattr(value, "instance"):
            session = value.instance
            option["attrs"]["data-capacity"] = session_capacity_summary(session, self.booking)
            option["attrs"]["data-play-mode"] = session.play_mode
            option["attrs"]["data-supervised-capacity"] = session.supervised_capacity
            option["attrs"]["data-started"] = "1" if session.starts_at <= timezone.now() else "0"
        return option


class TestBookingForm(forms.Form):
    estimate_token = forms.CharField(required=False, widget=forms.HiddenInput)
    customer = CustomerChoice(queryset=Customer.objects.order_by("last_name", "pk"))
    session_date = forms.DateField(
        required=False, label="Session date", widget=forms.DateInput(attrs={"type": "date"})
    )
    session = forms.ModelChoiceField(queryset=Session.objects.none())
    supervised = forms.BooleanField(required=False, label="Supervised Play")
    supervised_exception = forms.BooleanField(
        required=False,
        label="This session is marked as open play only. Change this booking only to supervised play (owner override).",
    )
    children = forms.IntegerField(
        min_value=0, max_value=32767, initial=1, label="Children ages 1–11"
    )
    adults = forms.IntegerField(min_value=0, max_value=32767, initial=1, label="Adults ages 12+")
    babies = forms.IntegerField(min_value=0, max_value=32767, initial=0, label="Babies under one")
    socks = forms.IntegerField(min_value=0, max_value=2147483647, initial=0, label="Grip socks")
    expected_method = forms.ChoiceField(
        choices=Booking._meta.get_field("expected_method").choices, label="Expected payment method"
    )
    special_admissions = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=14,
        decimal_places=2,
        label="Owner: adjust admissions price (optional)",
        help_text="Keep the agreed admissions total or adjust it here. Socks remain separate; attendee changes do not add an automatic cancellation fee.",
    )
    zelle_sender = forms.CharField(
        required=False, max_length=160, label="Zelle sender name/account"
    )
    override_capacity = forms.BooleanField(required=False, label="Owner: override session capacity")
    close_session = forms.BooleanField(
        required=False,
        label="Close this entire session to additional reservations",
        help_text="Existing bookings remain. Separate closures are removed only by an explicit reopening action.",
    )
    reopen_affected_sessions = forms.BooleanField(
        required=False,
        label="Reopen affected sessions when moving this booking",
        help_text="Removes only this booking/custom session’s blocks; separate closures stay in place.",
    )
    creation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput, required=False)

    def __init__(self, *args, owner=False, booking=None, customer=None, previewing=False, **kwargs):
        self.previewing = previewing
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
                    "zelle_sender",
                    "supervised",
                    "session",
                )
            }
            initial["version"] = booking.edit_version
        super().__init__(*args, initial=initial, **kwargs)
        self.fields["session"].widget = SessionChoiceSelect(booking=booking)
        self.fields["session"].queryset = Session.objects.filter(
            Q(source_slot__isnull=True)
            | Q(source_slot__active=True, source_slot__archived_at__isnull=True),
            ends_at__gt=timezone.now(),
            closed=False,
            kind=Session.Kind.ORDINARY,
        ).exclude(starts_at__date__in=CalendarDate.objects.filter(closed=True).values("day"))
        if not owner:
            for name in ("override_capacity", "close_session", "reopen_affected_sessions"):
                self.fields.pop(name)
        if booking:
            for field in ("customer", "creation_key"):
                self.fields.pop(field)
            self.fields["version"].required = True
        else:
            self.fields.pop("version")
            self.fields.pop("estimate_token")
        from .forms import payment_method_choices

        old_quote = booking.quotes.first() if booking else None
        self.fields["expected_method"].choices = payment_method_choices(
            old_quote.policy if old_quote else PricingPolicy.objects.first()
        )
        if not owner or not booking:
            self.fields.pop("supervised_exception")
        if not booking:
            self.fields.pop("reopen_affected_sessions", None)
        if (booking and booking.workflow != "integrated_v1") or (
            not booking and not settings.BOOKING_COMPLETION_ENABLED
        ):
            self.fields.pop("zelle_sender")
        from .payments.models import BookingChargeState

        special = BookingChargeState.objects.filter(booking=booking).first() if booking else None
        if not owner or not special or special.special_subtotal is None or special.comped:
            self.fields.pop("special_admissions")
        else:
            self.initial["special_admissions"] = special.special_subtotal
        session_date_picker(self, booking)
        customer_picker(self)

    def clean(self):
        data = super().clean()
        if data.get("supervised") and data.get("adults", 0) > 0:
            self.add_error("adults", "Cannot have adults in a supervised play visit.")
        if "zelle_sender" in self.fields and data.get("expected_method") == "zelle":
            from .payments.receipts import sender

            try:
                data["zelle_sender"] = sender(
                    data.get("zelle_sender", ""), required=not self.previewing
                )
            except forms.ValidationError as error:
                self.add_error("zelle_sender", error)
        return data


class TimingForm(forms.Form):
    session_date = forms.DateField(
        required=False, label="Session date", widget=forms.DateInput(attrs={"type": "date"})
    )
    session = forms.ModelChoiceField(queryset=Session.objects.none())
    version = forms.IntegerField(widget=forms.HiddenInput, min_value=1)
    override_capacity = forms.BooleanField(required=False, label="Owner: override session capacity")
    close_session = forms.BooleanField(
        required=False,
        label="Close this entire session to additional reservations",
        help_text="Existing bookings remain. Separate closures are removed only by an explicit reopening action.",
    )
    reopen_affected_sessions = forms.BooleanField(
        required=False,
        label="Reopen affected sessions when moving this booking",
        help_text="Removes only this booking/custom session’s blocks; separate closures stay in place.",
    )

    def __init__(self, *args, booking, owner=False, **kwargs):
        super().__init__(
            *args,
            initial={"session": booking.session_id, "version": booking.edit_version},
            **kwargs,
        )
        self.fields["session"].widget = SessionChoiceSelect(booking=booking)
        self.fields["session"].queryset = Session.objects.filter(
            Q(source_slot__isnull=True)
            | Q(source_slot__active=True, source_slot__archived_at__isnull=True),
            ends_at__gt=timezone.now(),
            closed=False,
            kind=Session.Kind.ORDINARY,
        ).exclude(starts_at__date__in=CalendarDate.objects.filter(closed=True).values("day"))
        if not owner:
            for name in ("override_capacity", "close_session", "reopen_affected_sessions"):
                self.fields.pop(name)

        session_date_picker(self, booking)


class PercentageField(forms.DecimalField):
    def to_python(self, value):
        number = super().to_python(value)
        return number.normalize() if number is not None and number.is_finite() else number


class PricingPolicyForm(forms.ModelForm):
    tax_percent = PercentageField(
        min_value=0, max_value=100, decimal_places=2, label="Staging sales tax (%)"
    )
    fee_percent = PercentageField(
        min_value=0, max_value=100, decimal_places=2, label="Card processing fee (%)"
    )

    class Meta:
        model = PricingPolicy
        fields = (
            "child_price",
            "extra_adult_price",
            "supervised_price",
            "sock_price",
        )

    def __init__(self, *args, policy=None, **kwargs):
        initial = {name: getattr(policy, name) for name in self.Meta.fields} if policy else {}
        if policy:
            initial.update(
                tax_percent=(policy.tax_rate * 100).quantize(Decimal(".01")),
                fee_percent=(policy.card_fee_rate * 100).quantize(Decimal(".01")),
            )
        # Never bind an existing immutable policy as this ModelForm's instance.
        super().__init__(*args, initial=initial, **kwargs)

    def clean(self):
        result = super().clean()
        if "child_price" in result:
            self.instance.minimum_admission = result["child_price"]
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
    field.widget.choices = [("", "Select a customer from the search results")] + (
        [(row.pk, field.label_from_instance(row))] if row else []
    )
    field.widget.attrs["data-customer-picker"] = "true"
