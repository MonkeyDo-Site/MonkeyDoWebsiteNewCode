from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import SiteSettings, WeeklySlot
from .permissions import staff_permission
from .recurring import FIELDS, generate_sessions, save_horizon, save_slot

WEEKDAYS = [
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
    (6, "Sunday"),
]


class SlotForm(forms.ModelForm):
    weekdays = forms.TypedMultipleChoiceField(
        choices=WEEKDAYS, coerce=int, widget=forms.CheckboxSelectMultiple
    )
    visibility = forms.ChoiceField(
        choices=[("", "Choose visibility"), ("private", "Backend only"), ("public", "Public")]
    )
    revision = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = WeeklySlot
        fields = tuple(field for field in FIELDS if field != "public")
        widgets = {
            "starts_at": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "ends_at": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
        }
        labels = {"label": "Internal label", "active": "Active weekly template"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial.update(
                visibility="public" if self.instance.public else "private",
                revision=self.instance.revision,
            )
            self.fields["revision"].required = True


class GenerationForm(forms.Form):
    slots = forms.ModelMultipleChoiceField(
        queryset=WeeklySlot.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Weekly templates",
    )
    from_day = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), label="From date (inclusive)"
    )
    through_day = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), label="Through date (inclusive)"
    )
    update_existing = forms.BooleanField(
        required=False,
        label="Also update untouched, unbooked generated sessions in this date range",
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
    row = get_object_or_404(WeeklySlot, pk=pk) if pk else None
    form = SlotForm(request.POST if request.method == "POST" else None, instance=row)
    if request.method == "POST" and form.is_valid():
        data = {key: form.cleaned_data[key] for key in FIELDS if key != "public"}
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
                "Weekly template saved. Review a date range and generate/apply sessions to use it; existing bookings were not changed.",
            )
            return redirect("recurring_settings")
    return render(
        request,
        "core/recurring_form.html",
        {"form": form, "heading": "Edit weekly template" if pk else "Add weekly template"},
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
            messages.success(
                request,
                "Generation complete. Existing bookings and manual edits were preserved; no messages or payments were processed.",
            )
    return render(
        request,
        "core/recurring_settings.html",
        {"slots": WeeklySlot.objects.all(), "form": form, "results": results},
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
