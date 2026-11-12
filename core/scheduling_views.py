from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_safe

from .availability import NEW_YORK, occupancy
from .calendar import date_closed, weekly_default_blocked
from .models import CalendarDate, Session
from .permissions import staff_permission
from .recurring import local_time
from .scheduling import SESSION_FIELDS, save_date, save_session


class SessionForm(forms.ModelForm):
    visibility = forms.ChoiceField(
        choices=[("", "Choose visibility"), ("private", "Backend only"), ("public", "Public")]
    )
    revision = forms.IntegerField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Session
        fields = tuple(name for name in SESSION_FIELDS if name != "public")
        widgets = {
            "starts_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "ends_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
        }
        labels = {
            "private_label": "Internal session label",
            "closed": "Close this session to new reservations",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["private_label"].required = True
        if self.instance.pk:
            self.initial.update(
                visibility="public" if self.instance.public else "private",
                revision=self.instance.revision,
            )
            if self.instance.play_mode == "both" and self.instance.supervised_capacity == 0:
                self.initial["play_mode"] = "accompanied"
            self.fields["revision"].required = True
            for name, label in (("starts_at", "Starts at"), ("ends_at", "Ends at")):
                self.fields[name] = forms.TimeField(
                    label=label,
                    input_formats=["%I:%M %p", "%I %p", "%H:%M"],
                    widget=forms.TimeInput(format="%I:%M %p", attrs={"placeholder": "2:30 PM"}),
                    help_text="New York time, for example 2:30 PM.",
                )
                self.initial[name] = getattr(self.instance, name).astimezone(NEW_YORK).time()
        else:
            self.initial["play_mode"] = "accompanied"

    def clean(self):
        data = super().clean()
        if self.instance.pk:
            day = self.instance.starts_at.astimezone(NEW_YORK).date()
            for name in ("starts_at", "ends_at"):
                if name in data:
                    try:
                        data[name] = local_time(day, data[name])
                    except ValidationError as exc:
                        self.add_error(name, exc)
        return data


class DateForm(forms.Form):
    day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    closed = forms.BooleanField(required=False, label="Close date to new reservations.")
    private_reason = forms.CharField(max_length=500, required=False, widget=forms.Textarea)
    chol_hamoed = forms.BooleanField(required=False, label="Chol Hamoed date")
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


def owner(request):
    if not request.user.is_superuser:
        raise PermissionDenied


@staff_permission("core.change_session")
@require_safe
def scheduling(request):
    owner(request)
    day_form = forms.DateField()
    try:
        day = day_form.clean(
            request.GET.get("day", timezone.localdate(timezone=NEW_YORK).isoformat())
        )
    except ValidationError:
        day = timezone.localdate(timezone=NEW_YORK)
    rows = Session.objects.filter(starts_at__date=day).select_related("source_slot")
    return render(
        request,
        "core/scheduling.html",
        {
            "day": day,
            "sessions": [
                {
                    "session": row,
                    "counts": occupancy(row),
                    "blocked": row.closed or date_closed(row) or weekly_default_blocked(row),
                    "visible": row.public
                    and not weekly_default_blocked(row)
                    and day.weekday() != 5,
                }
                for row in rows
            ],
            "date_rule": CalendarDate.objects.filter(day=day).first(),
        },
    )


@staff_permission("core.change_session")
@require_http_methods(["GET", "POST"])
def session_edit(request, pk=None):
    owner(request)
    row = get_object_or_404(Session, pk=pk) if pk else None
    form = SessionForm(request.POST if request.method == "POST" else None, instance=row)
    if request.method == "POST" and form.is_valid():
        data = {name: form.cleaned_data[name] for name in SESSION_FIELDS if name != "public"}
        data["public"] = form.cleaned_data["visibility"] == "public"
        try:
            saved = save_session(
                actor=request.user, data=data, pk=pk, revision=form.cleaned_data.get("revision")
            )
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(
                request,
                "Session saved. Existing reservations and quotes were preserved; no messages were sent.",
            )
            return redirect(
                f"/staff/scheduling/?day={saved.starts_at.astimezone(NEW_YORK).date().isoformat()}"
            )
    return render(
        request,
        "core/scheduling_form.html",
        {
            "form": form,
            "heading": "Edit session" if pk else "Add one-time session",
            "session_day": row.starts_at.astimezone(NEW_YORK).date() if row else None,
        },
    )


@staff_permission("core.change_calendardate")
@require_http_methods(["GET", "POST"])
def date_edit(request):
    owner(request)
    select = forms.Form(request.GET)
    select.fields["day"] = forms.DateField()
    day = select.cleaned_data["day"] if select.is_valid() else timezone.localdate(timezone=NEW_YORK)
    row = CalendarDate.objects.filter(day=day).first()
    initial = {
        "day": day,
        "closed": row.closed if row else False,
        "private_reason": row.private_reason if row else "",
        "chol_hamoed": row.chol_hamoed if row else False,
        "revision": row.revision if row else 0,
    }
    form = DateForm(request.POST if request.method == "POST" else None, initial=initial)
    form.fields["day"].disabled = True
    form.fields["day"].label = "Date"
    if request.method == "POST" and form.is_valid():
        # Day must match the loaded date; changing the date requires loading its
        # current revision rather than applying one date's revision to another.
        if form.cleaned_data["day"] != day:
            form.add_error("day", "Load this date from the scheduling page before editing it.")
        else:
            try:
                save_date(actor=request.user, **form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                messages.success(
                    request,
                    "Date settings saved. Existing bookings were not cancelled or repriced; no messages were sent.",
                )
                return redirect(f"/staff/scheduling/?day={day.isoformat()}")
    return render(request, "core/scheduling_form.html", {"form": form, "heading": "Date settings"})
