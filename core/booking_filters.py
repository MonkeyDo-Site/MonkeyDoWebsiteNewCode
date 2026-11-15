"""Shared date-bounded staff booking filters; Today fixes the date server-side."""

from datetime import datetime, time, timedelta

from django import forms
from django.db.models import BooleanField, Case, Q, Value, When
from django.utils import timezone

from .availability import NEW_YORK, occupancy
from .calendar import date_closed, weekly_default_blocked
from .forms import phone_search_digits
from .models import Booking, Session
from .name_matching import match_rank, name_candidates


class BookingFilters(forms.Form):
    start = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), label="From date")
    end = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), label="Through date")
    q = forms.CharField(max_length=120, required=False, label="Family name, phone or email")
    session = forms.ChoiceField(required=False, label="Session", choices=[])
    play = forms.MultipleChoiceField(
        required=False,
        choices=[("open", "Open Play"), ("supervised", "Supervised Play")],
        widget=forms.CheckboxSelectMultiple,
    )
    status = forms.MultipleChoiceField(
        required=False,
        choices=[
            ("pending", "Setup pending"),
            ("upcoming", "Upcoming"),
            ("cancelled", "Cancelled"),
            ("arrived", "Arrived"),
            ("no_show", "No show"),
        ],
        widget=forms.CheckboxSelectMultiple,
    )
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Session order"),
            *[
                (f"{sign}{field}", f"{field.title()}: {label}")
                for field in ("children", "adults", "babies")
                for sign, label in (("", "Low to high"), ("-", "High to low"))
            ],
        ],
    )

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end"):
            if data["end"] < data["start"]:
                self.add_error("end", "Choose an end date on or after the start date.")
            elif (data["end"] - data["start"]).days > 730:
                self.add_error("end", "Choose a range of no more than two years.")
        return data


def booking_context(request, *, today_only=False):
    today = timezone.localdate(timezone=NEW_YORK)
    data = request.GET.copy()
    data.setdefault("start", today.isoformat())
    data.setdefault("end", data["start"])
    if today_only:
        data["start"] = data["end"] = today.isoformat()
    form = BookingFilters(data)
    # Validate dates independently to build the permitted session picker safely.
    try:
        start = form.fields["start"].clean(data.get("start"))
        end = form.fields["end"].clean(data.get("end"))
        if end < start or (end - start).days > 730:
            raise forms.ValidationError("Invalid range")
    except forms.ValidationError:
        start = end = today
    begin = datetime.combine(start, time.min, NEW_YORK)
    finish = datetime.combine(end + timedelta(days=1), time.min, NEW_YORK)
    sessions = list(
        Session.objects.filter(starts_at__gte=begin, starts_at__lt=finish).select_related(
            "source_slot"
        )
    )
    if today_only:
        form.fields["session"].choices = [("", "All sessions")] + [
            (str(s.pk), str(s)) for s in sessions
        ]
    else:
        clocks = sorted(
            {timezone.localtime(s.starts_at, NEW_YORK).strftime("%H:%M") for s in sessions}
        )
        form.fields["session"].choices = [("", "All session times")] + [
            (clock, datetime.strptime(clock, "%H:%M").strftime("%I:%M %p")) for clock in clocks
        ]
    for field in form.fields.values():
        field.widget.attrs["form"] = "booking-filter-form"
    sort_links = {}
    for key in ("children", "adults", "babies"):
        params = request.GET.copy()
        params.pop("page", None)
        params["sort"] = "-" + key if data.get("sort") == key else key
        sort_links[key] = "?" + params.urlencode()
    valid = form.is_valid()
    rows = Booking.objects.select_related("customer", "session").filter(
        session__starts_at__gte=begin, session__starts_at__lt=finish
    )
    possible = []
    if not valid:
        rows = rows.none()
    else:
        filters = form.cleaned_data
        query = filters["q"].strip()
        if query:
            exact, possible = name_candidates(query)
            criteria = (
                Q(customer__last_name__icontains=query)
                | Q(customer__email__icontains=query)
                | Q(customer__previous_email__icontains=query)
                | Q(customer_id__in=exact + possible)
            )
            digits = phone_search_digits(query)
            if digits:
                criteria |= Q(customer__phone__contains=digits) | Q(
                    customer__previous_phone__contains=digits
                )
            rows = rows.filter(criteria)
        else:
            exact = []
        if filters["session"]:
            ids = [
                s.pk
                for s in sessions
                if (
                    str(s.pk)
                    if today_only
                    else timezone.localtime(s.starts_at, NEW_YORK).strftime("%H:%M")
                )
                == filters["session"]
            ]
            rows = rows.filter(session_id__in=ids)
        if len(filters["play"]) == 1:
            rows = rows.filter(supervised=filters["play"][0] == "supervised")
        if filters["status"]:
            status = Q(
                attendance__in=[s for s in filters["status"] if s not in {"pending", "upcoming"}]
            )
            if "pending" in filters["status"]:
                status |= Q(attendance__isnull=True, setup_pending=True)
            if "upcoming" in filters["status"]:
                status |= Q(attendance__isnull=True, setup_pending=False)
            rows = rows.filter(status)
        order = ["session__starts_at", "created_at", "pk"]
        if query:
            order.insert(0, match_rank("customer_id", exact, possible))
        if filters["sort"]:
            order.insert(0, filters["sort"])
        rows = rows.order_by(*order)
    rows = rows.annotate(
        possible_name_match=Case(
            When(customer_id__in=possible, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
    )
    overview = []
    for session in sessions:
        children, adults, supervised = occupancy(session)
        overview.append(
            {
                "session": session,
                "bookable": session.kind == Session.Kind.ORDINARY
                and not session.closed
                and not date_closed(session)
                and not weekly_default_blocked(session)
                and session.ends_at > timezone.now()
                and not (session.play_mode == "supervised" and session.starts_at <= timezone.now()),
                "bookings": session.bookings.exclude(attendance="cancelled").count(),
                "children": children,
                "adults": adults,
                "supervised": supervised,
            }
        )
    selected_session = form.cleaned_data.get("session") if valid and today_only else None
    if selected_session:
        overview = [item for item in overview if str(item["session"].pk) == selected_session]
    params = request.GET.copy()
    params.pop("page", None)
    return {
        "selected_session": selected_session,
        "filter_form": form,
        "sort_links": sort_links,
        "rows": rows,
        "session_overview": overview,
        "today_only": today_only,
        "query": data.get("q", ""),
        "filter_query": params.urlencode(),
        "link_customers": True,
        "matching_count": rows.count(),
    }
