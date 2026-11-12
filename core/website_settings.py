"""Owner website-content visibility controls; no scheduling or booking mutation."""

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .models import AuditEvent, SiteSettings
from .permissions import require_actor, staff_permission


class WebsiteSettingsForm(forms.Form):
    clubs_visible = forms.BooleanField(required=False, label="Show clubs on the website")
    expected_clubs_visible = forms.IntegerField(min_value=0, max_value=1, widget=forms.HiddenInput)


@transaction.atomic
def save_club_visibility(*, actor, clubs_visible, expected_clubs_visible):
    require_actor(actor, "core.change_sitesettings", owner=True)
    if type(clubs_visible) is not bool or type(expected_clubs_visible) is not bool:
        raise ValidationError("Choose a valid club visibility setting.")
    SiteSettings.objects.get_or_create(pk=1, defaults={"clubs_visible": False})
    site = SiteSettings.objects.select_for_update().get(pk=1)
    if site.clubs_visible != expected_clubs_visible:
        raise ValidationError("Website settings changed. Reload before saving.")
    if site.clubs_visible == clubs_visible:
        return site
    before = site.clubs_visible
    site.clubs_visible = clubs_visible
    site.save(update_fields=["clubs_visible"])
    AuditEvent.objects.create(
        actor=actor,
        action="website.clubs_visibility_changed",
        record_type="settings",
        record_id="1",
        changes={"before": {"clubs_visible": before}, "after": {"clubs_visible": clubs_visible}},
    )
    return site


@staff_permission("core.change_sitesettings")
@require_http_methods(["GET", "POST"])
def website_settings(request):
    require_actor(request.user, "core.change_sitesettings", owner=True)
    site = SiteSettings.objects.filter(pk=1).first()
    visible = site.clubs_visible if site else False
    form = WebsiteSettingsForm(
        request.POST if request.method == "POST" else None,
        initial={"clubs_visible": visible, "expected_clubs_visible": int(visible)},
    )
    if request.method == "POST" and form.is_valid():
        try:
            site = save_club_visibility(
                actor=request.user,
                clubs_visible=form.cleaned_data["clubs_visible"],
                expected_clubs_visible=bool(form.cleaned_data["expected_clubs_visible"]),
            )
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            status = "visible" if site.clubs_visible else "hidden"
            messages.success(request, f"Website settings saved. Clubs are now {status}.")
            return redirect("website_settings")
    return render(request, "core/website_settings.html", {"form": form})
