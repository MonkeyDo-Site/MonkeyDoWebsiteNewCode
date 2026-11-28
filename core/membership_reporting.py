"""Operational membership filters share the actual installment funding facts."""

from datetime import timedelta

from django import forms
from django.db.models import Case, CharField, DateField, Exists, F, OuterRef, Q, Value, When
from django.db.models.functions import Cast, Least

from .forms import phone_search_digits
from .membership_funding import held_members
from .membership_notices import installment_balances
from .membership_records import MembershipInstallment, MembershipPurchase
from .membership_sales import today
from .name_matching import match_rank, name_candidates

STATUSES = [
    (key, key.title())
    for key in ("active", "scheduled", "pending", "overdue", "review", "expired", "cancelled")
]


class MembershipFilters(forms.Form):
    q = forms.CharField(
        required=False,
        max_length=120,
        label="Customer or membership",
        widget=forms.TextInput(attrs={"placeholder": "Name, phone, email or M number"}),
    )
    customer = forms.IntegerField(
        required=False, min_value=1, max_value=9223372036854775807, widget=forms.HiddenInput
    )
    kind = forms.ChoiceField(
        required=False,
        label="Membership",
        choices=[("", "All types"), ("subscription", "Subscription"), ("unlimited", "Unlimited")],
    )
    status = forms.ChoiceField(required=False, choices=[("", "All statuses"), *STATUSES])
    expiry = forms.ChoiceField(
        required=False,
        label="Expiry",
        choices=[("", "All dates"), ("soon", "Next 5 days"), ("custom", "Choose end dates")],
    )
    ends_from = forms.DateField(
        required=False, label="Ends from", widget=forms.DateInput(attrs={"type": "date"})
    )
    ends_to = forms.DateField(
        required=False, label="Ends through", widget=forms.DateInput(attrs={"type": "date"})
    )

    def clean(self):
        values = super().clean()
        start, end = values.get("ends_from"), values.get("ends_to")
        if start and end and start > end:
            self.add_error("ends_to", "The last end date must be on or after the first.")
        return values


def reporting_members(*, on=None):
    on = on or today()
    unpaid = installment_balances(on=on, due_only=False).filter(purchase_id=OuterRef("pk"))
    required = MembershipInstallment.objects.filter(purchase_id=OuterRef("pk")).exclude(
        Q(purchase__billing_state__stopped_on__isnull=False)
        & Q(cycle__starts_on__gte=F("purchase__billing_state__stopped_on"))
    )
    return (
        MembershipPurchase.objects.select_related("membership", "customer", "billing_state")
        .annotate(
            effective_ends_on=Case(
                When(billing_state__stopped_on__isnull=True, then=F("membership__ends_on")),
                default=Least(
                    F("membership__ends_on"),
                    Cast(F("billing_state__stopped_on") - timedelta(days=1), DateField()),
                ),
                output_field=DateField(),
            ),
            _unpaid_first=Exists(unpaid.filter(number=1)),
            _has_installments=Exists(required),
            _unpaid_due=Exists(unpaid.filter(due_on__lte=on)),
        )
        .annotate(
            report_status=Case(
                When(
                    Q(billing_state__stopped_on__lte=on)
                    | Q(billing_state__stopped_on__lte=F("membership__starts_on")),
                    then=Value("cancelled"),
                ),
                When(membership__ends_on__lt=on, then=Value("expired")),
                When(pk__in=held_members(on=on), then=Value("review")),
                When(
                    ~Q(purpose="complimentary")
                    & (Q(_unpaid_first=True) | Q(_has_installments=False)),
                    then=Value("pending"),
                ),
                When(~Q(purpose="complimentary") & Q(_unpaid_due=True), then=Value("overdue")),
                When(membership__starts_on__gt=on, then=Value("scheduled")),
                default=Value("active"),
                output_field=CharField(),
            )
        )
    )


def filtered_members(params):
    form = MembershipFilters(params)
    records = reporting_members()
    possible = []
    if not form.is_valid():
        return records.none(), form, possible
    values = form.cleaned_data
    if values["customer"]:
        records = records.filter(customer_id=values["customer"])
    if values["kind"]:
        records = records.filter(membership__kind=values["kind"])
    if values["status"]:
        records = records.filter(report_status=values["status"])
    if values["expiry"] == "soon":
        records = records.filter(
            effective_ends_on__range=(today(), today() + timedelta(days=5))
        ).exclude(report_status="cancelled")
    elif values["expiry"] == "custom" or values["ends_from"] or values["ends_to"]:
        if values["ends_from"]:
            records = records.filter(effective_ends_on__gte=values["ends_from"])
        if values["ends_to"]:
            records = records.filter(effective_ends_on__lte=values["ends_to"])
    query = values["q"].strip()
    if query:
        exact, possible = name_candidates(query)
        match = (
            Q(customer__last_name__icontains=query)
            | Q(customer__email__icontains=query)
            | Q(customer__previous_email__icontains=query)
            | Q(customer_id__in=exact + possible)
        )
        digits = phone_search_digits(query)
        if digits:
            match |= Q(customer__phone__contains=digits) | Q(
                customer__previous_phone__contains=digits
            )
        number = query.removeprefix("#").removeprefix("M").removeprefix("m")
        if number.isascii() and number.isdigit() and len(number) <= 18:
            match |= Q(pk=int(number))
            if query == number:
                match |= Q(customer_id=int(number))
        records = records.filter(match).order_by(
            match_rank("customer_id", exact, possible), "-accepted_at", "-pk"
        )
    else:
        records = records.order_by("-accepted_at", "-pk")
    return records, form, possible
