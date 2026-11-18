from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_safe

from .availability import NEW_YORK, occupancy
from .calendar import date_backend_only, date_closed, reservation_blocked, weekly_default_blocked
from .models import CalendarDate, Session
from .permissions import staff_permission
from .recurring import local_time
from .scheduling import SESSION_FIELDS, save_date, save_session


class SessionForm(forms.ModelForm):
    reopen_affected_sessions = forms.BooleanField(
        required=False,
        label="Reopen sessions no longer overlapped by this custom time",
        help_text="Removes only this custom session’s blocks; separate closures remain.",
    )
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
            "closed": "Closed for reservation",
            "custom_blocking": "Custom one-time session that blocks conflicting sessions",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["play_mode"].choices = [
            ("accompanied", "Open Play only"),
            ("supervised", "Supervised Play only"),
            ("both", "Open Play and Supervised Play"),
        ]
        self.fields["private_label"].required = True
        if not self.instance.pk or not self.instance.custom_blocking:
            self.fields.pop("reopen_affected_sessions", None)
        if self.instance.pk:
            self.fields["custom_blocking"].disabled = True
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
    closed = forms.BooleanField(required=False, label="Closed for reservation")
    backend_only = forms.BooleanField(
        required=False, label="Backend only — hide all sessions on this date from the public"
    )
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
                    "blocked": row.closed
                    or date_closed(row)
                    or reservation_blocked(row)
                    or weekly_default_blocked(row),
                    "visible": row.public
                    and not date_backend_only(row)
                    and not weekly_default_blocked(row),
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
    conflicts = []
    preview = None
    preview_token = None
    if request.method == "POST" and form.is_valid():
        data = {name: form.cleaned_data[name] for name in SESSION_FIELDS if name != "public"}
        data["public"] = form.cleaned_data["visibility"] == "public"
        try:
            if data["custom_blocking"]:
                from django.core import signing

                from .session_blocks import custom_preview

                preview, preview_token, payload = custom_preview({**data, "pk": pk})
                try:
                    supplied = signing.loads(
                        request.POST.get("custom_preview", ""),
                        salt="custom-session-preview",
                        max_age=1200,
                    )
                except signing.BadSignature:
                    supplied = None
                # JSON round-trip represents tuples as arrays.
                import json

                if supplied != json.loads(json.dumps(payload)):
                    return render(
                        request,
                        "core/scheduling_form.html",
                        {
                            "form": form,
                            "heading": "Review custom session",
                            "custom_preview": preview,
                            "custom_preview_token": preview_token,
                        },
                    )
            saved = save_session(
                actor=request.user,
                data=data,
                pk=pk,
                revision=form.cleaned_data.get("revision"),
                reopen_affected_sessions=form.cleaned_data.get("reopen_affected_sessions", False),
                expected_conflicts=payload["sessions"] if data["custom_blocking"] else None,
            )
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
            conflicts = getattr(exc, "bookings", [])
        else:
            messages.success(
                request,
                "Session saved. Existing reservations and quotes were preserved; no messages were sent.",
            )
            return redirect(
                f"/staff/scheduling/?day={saved.starts_at.astimezone(NEW_YORK).date().isoformat()}"
            )
    from .calendar import (
        date_closed,
        weekly_default_blocked,
    )

    blockers = []
    if row:
        for block in row.reservation_blocks.filter(active=True).select_related(
            "source_session", "booking"
        ):
            blockers.append(
                {
                    "label": "Blocked by custom session"
                    if block.source_session_id
                    else f"Closed from booking #{block.booking_id}",
                    "url": f"/staff/scheduling/{block.source_session_id}/"
                    if block.source_session_id
                    else f"/staff/bookings/{block.booking_id}/",
                }
            )
        if weekly_default_blocked(row):
            blockers.append(
                {
                    "label": "Its weekly default is closed or deleted",
                    "url": "/staff/scheduling/weekly/",
                }
            )
        if date_closed(row):
            blockers.append(
                {
                    "label": "This date is closed",
                    "url": f"/staff/scheduling/date/?day={row.starts_at.astimezone(NEW_YORK).date().isoformat()}",
                }
            )
    return render(
        request,
        "core/scheduling_form.html",
        {
            "form": form,
            "conflicting_bookings": conflicts,
            "session": row,
            "custom_blocks": row.caused_blocks.filter(active=True).select_related("session")
            if row
            else [],
            "heading": "Edit session" if pk else "Add one-time session",
            "blockers": blockers,
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
        "backend_only": row.backend_only if row else False,
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


@staff_permission("core.change_session")
@require_http_methods(["POST"])
def reopen_custom_session(request, pk):
    owner(request)
    from .session_blocks import reopen_custom

    try:
        if request.POST.get("confirm_reopen") != "on":
            raise ValidationError(
                "Confirm that affected sessions should reopen. Separate closures will remain."
            )
        reopen_custom(request.user, pk, int(request.POST.get("revision", "")))
    except (ValueError, ValidationError) as exc:
        messages.error(
            request,
            " ".join(exc.messages)
            if isinstance(exc, ValidationError)
            else "Reload the session before reopening its affected sessions.",
        )
    else:
        messages.success(
            request,
            "This custom session is closed. Its blocks were removed; independent closures remain.",
        )
    return redirect("session_edit", pk=pk)
