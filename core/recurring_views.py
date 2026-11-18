from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .date_display import weekday_name
from .models import Booking, SiteSettings, WeeklySlot
from .permissions import staff_permission
from .recurring import FIELDS, delete_slot, generate_sessions, save_horizon, save_slot
from .templatetags.scheduling_labels import display_session_label

WEEKDAYS = [(day, weekday_name(day)) for day in (6, 0, 1, 2, 3, 4, 5)]


class SlotForm(forms.ModelForm):
    closed = forms.BooleanField(required=False, initial=False, label="Closed for reservation")
    weekdays = forms.TypedMultipleChoiceField(
        choices=WEEKDAYS, coerce=int, widget=forms.CheckboxSelectMultiple
    )
    visibility = forms.ChoiceField(
        choices=[("", "Choose visibility"), ("private", "Backend only"), ("public", "Public")]
    )
    revision = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = WeeklySlot
        fields = tuple(field for field in FIELDS if field not in {"public", "active"})
        widgets = {
            "starts_at": forms.TimeInput(format="%I:%M %p", attrs={"placeholder": "2:30 PM"}),
            "ends_at": forms.TimeInput(format="%I:%M %p", attrs={"placeholder": "3:45 PM"}),
        }
        labels = {"label": "Internal label", "active": "Open for reservation"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["play_mode"].choices = [
            ("accompanied", "Open Play only"),
            ("supervised", "Supervised Play only"),
            ("both", "Open Play and Supervised Play"),
        ]
        for name in ("starts_at", "ends_at"):
            self.fields[name].input_formats = ["%I:%M %p", "%I %p", "%H:%M"]
        self.fields["closed"].help_text = (
            "Closed defaults cannot generate sessions. Their existing sessions are immediately "
            "hidden from customer booking and closed to new reservations. Existing bookings keep their times."
        )
        if self.instance.pk:
            self.initial.update(
                visibility="public" if self.instance.public else "private",
                revision=self.instance.revision,
                closed=not self.instance.active,
            )
            self.fields["revision"].required = True


class WeeklyDefaultChoice(forms.ModelMultipleChoiceField):
    def label_from_instance(self, slot):
        return display_session_label(slot.label, slot.starts_at)


class GenerationForm(forms.Form):
    slots = WeeklyDefaultChoice(
        queryset=WeeklySlot.objects.filter(active=True, archived_at__isnull=True),
        widget=forms.CheckboxSelectMultiple,
        label="Open weekly defaults",
    )
    from_day = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), label="From date (inclusive)"
    )
    through_day = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), label="Through date (inclusive)"
    )
    update_existing = forms.BooleanField(
        required=False,
        label="Also apply changes to existing unbooked sessions",
        help_text="Adds missing sessions either way. When checked, also updates existing generated sessions that have no booking history or individual edits.",
    )


class HorizonForm(forms.Form):
    days = forms.IntegerField(
        min_value=1, max_value=10, label="Advance booking horizon (calendar days)"
    )
    expected_days = forms.IntegerField(widget=forms.HiddenInput)
    reset_confirmed = forms.BooleanField(
        required=False, label="Confirm reverting to default: 1 day"
    )


@staff_permission("core.change_weeklyslot")
@require_http_methods(["GET", "POST"])
def slot_edit(request, pk=None):
    if not request.user.is_superuser:
        raise PermissionDenied
    row = get_object_or_404(WeeklySlot, pk=pk, archived_at__isnull=True) if pk else None
    form = SlotForm(request.POST if request.method == "POST" else None, instance=row)
    if request.method == "POST" and form.is_valid():
        data = {key: form.cleaned_data[key] for key in FIELDS if key not in {"public", "active"}}
        data["active"] = not form.cleaned_data["closed"]
        data["public"] = form.cleaned_data["visibility"] == "public"
        try:
            save_slot(
                actor=request.user, data=data, pk=pk, revision=form.cleaned_data.get("revision")
            )
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(
                request,
                "Weekly default saved. Generate sessions to apply timing or capacity changes. Deactivation blocks new reservations immediately; existing bookings keep their times.",
            )
            return redirect("recurring_settings")
    return render(
        request,
        "core/recurring_form.html",
        {
            "form": form,
            "heading": "Edit weekly default session" if pk else "Add a weekly default session",
            "slot": row,
        },
    )


@staff_permission("core.change_weeklyslot")
@staff_permission("core.change_session")
@require_http_methods(["GET", "POST"])
def recurring_settings(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    form = GenerationForm(request.POST if request.method == "POST" else None)
    results = None
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        data["slot_ids"] = [slot.pk for slot in data.pop("slots")]
        try:
            results = generate_sessions(actor=request.user, **data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            counts = {
                key: sum(result["outcome"] == key for result in results)
                for key in ("Created", "Updated", "Unchanged", "Preserved")
            }
            notify = messages.warning if counts["Preserved"] else messages.success
            notify(
                request,
                f"Created: {counts['Created']} · Updated: {counts['Updated']} · Unchanged: {counts['Unchanged']} · Not generated: {counts['Preserved']}. Review the dated results and reasons below. Existing bookings keep their times.",
            )
    return render(
        request,
        "core/recurring_settings.html",
        {
            "slots": weekly_coverage(),
            "form": form,
            "results": results,
        },
    )


@staff_permission("core.change_sitesettings")
@require_http_methods(["GET", "POST"])
def horizon_settings(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    current = (
        SiteSettings.objects.filter(pk=1).values_list("booking_horizon_days", flat=True).first()
        or 1
    )
    form = HorizonForm(
        request.POST if request.method == "POST" else None,
        initial={"days": current, "expected_days": current},
    )
    if request.method == "POST" and form.is_valid():
        try:
            data = dict(form.cleaned_data)
            if request.POST.get("reset_to_default") == "1":
                data["days"] = 1
            save_horizon(actor=request.user, **data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(
                request,
                "Booking horizon updated. Existing bookings are unchanged. Sunday still opens no later than Friday midnight.",
            )
            return redirect("horizon_settings")
    return render(request, "core/recurring_form.html", {"form": form, "heading": "Booking horizon"})


class DeleteSlotForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    expected_bookings = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    confirm = forms.BooleanField(
        label="I understand that existing bookings and their times will be retained."
    )


@staff_permission("core.change_weeklyslot")
@require_http_methods(["GET", "POST"])
def slot_delete(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    row = get_object_or_404(WeeklySlot, pk=pk, archived_at__isnull=True)
    count = Booking.objects.filter(session__source_slot=row).count()
    error = None
    form = DeleteSlotForm(
        request.POST if request.method == "POST" else None,
        initial={"revision": row.revision, "expected_bookings": count},
    )
    if request.method == "POST" and form.is_valid():
        try:
            delete_slot(
                actor=request.user,
                pk=pk,
                revision=form.cleaned_data["revision"],
                expected_bookings=form.cleaned_data["expected_bookings"],
            )
        except ValidationError as exc:
            row.refresh_from_db()
            count = Booking.objects.filter(session__source_slot=row).count()
            form = DeleteSlotForm(initial={"revision": row.revision, "expected_bookings": count})
            error = " ".join(exc.messages)
        else:
            messages.success(
                request,
                "Weekly default deleted. Its future sessions are hidden from customer booking; existing bookings and times were retained.",
            )
            return redirect("recurring_settings")
    return render(
        request,
        "core/weekly_delete.html",
        {"slot": row, "booking_count": count, "form": form, "error": error},
    )


@staff_permission("core.change_weeklyslot")
@require_http_methods(["GET", "POST"])
def schedule_edit(request):
    from django.forms import formset_factory

    from .recurring import save_slots

    if not request.user.is_superuser:
        raise PermissionDenied
    slots = list(WeeklySlot.objects.filter(archived_at__isnull=True).order_by("pk"))

    class BatchSlotForm(SlotForm):
        slot_id = forms.IntegerField(widget=forms.HiddenInput)

    forms_type = formset_factory(BatchSlotForm, extra=0, max_num=500, validate_max=True)
    initial = []
    for slot in slots:
        initial.append(
            {
                **{f: getattr(slot, f) for f in FIELDS if f != "public"},
                "closed": not slot.active,
                "slot_id": slot.pk,
                "revision": slot.revision,
                "visibility": "public" if slot.public else "private",
            }
        )
    formset = forms_type(request.POST if request.method == "POST" else None, initial=initial)
    error = None
    if request.method == "POST" and formset.is_valid():
        try:
            ids = [form.cleaned_data["slot_id"] for form in formset]
            if len(ids) != len(set(ids)) or set(ids) != {slot.pk for slot in slots}:
                raise ValidationError("Weekly schedule changed. Reload and review all defaults.")
            edits = []
            for form in formset:
                data = {k: form.cleaned_data[k] for k in FIELDS if k not in {"public", "active"}}
                data["active"] = not form.cleaned_data["closed"]
                data["public"] = form.cleaned_data["visibility"] == "public"
                edits.append(
                    {
                        "pk": form.cleaned_data["slot_id"],
                        "revision": form.cleaned_data["revision"],
                        "data": data,
                    }
                )
            save_slots(actor=request.user, edits=edits)
        except ValidationError as exc:
            error = " ".join(exc.messages)
        else:
            messages.success(
                request,
                "Weekly schedule saved together. Generate dated sessions with updates selected to apply the revised schedule to eligible dates.",
            )
            return redirect("recurring_settings")
    return render(request, "core/weekly_batch.html", {"formset": formset, "error": error})


def weekly_coverage():
    from .schedule_coverage import describe_coverage

    slots = list(WeeklySlot.objects.filter(archived_at__isnull=True))
    for slot in slots:
        slot.display_weekdays = sorted(slot.weekdays, key=lambda d: (d + 1) % 7)
        describe_coverage(slot)
    return slots
