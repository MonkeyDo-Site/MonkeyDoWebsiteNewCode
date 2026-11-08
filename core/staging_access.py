import uuid
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .account_security import allow_security_request
from .models import AuditEvent, SiteSettings
from .permissions import staff_permission

COOKIE = "monkeydo_staging_access"
SALT = "monkeydo-staging-gate"


def password_current(site):
    return bool(
        site
        and site.staging_password_hash
        and site.staging_password_changed_at
        and timezone.now() < site.staging_password_changed_at + timedelta(days=90)
    )


def access_valid(request, site):
    if not password_current(site):
        return False
    try:
        value = signing.loads(request.COOKIES.get(COOKIE, ""), salt=SALT, max_age=24 * 60 * 60)
        return value == str(site.staging_access_version)
    except (signing.BadSignature, ValueError):
        return False


def grant_access(response, site):
    response.set_cookie(
        COOKIE,
        signing.dumps(str(site.staging_access_version), salt=SALT),
        max_age=24 * 60 * 60,
        httponly=True,
        secure=settings.APP_ENV == "staging",
        samesite="Lax",
    )
    return response


@transaction.atomic
def set_staging_password(*, owner, password):
    if not owner.is_active or not owner.is_staff or not owner.is_superuser:
        raise PermissionDenied
    validate_password(password)
    SiteSettings.objects.get_or_create(pk=1)
    site = SiteSettings.objects.select_for_update().get(pk=1)
    site.staging_password_hash = make_password(password)
    site.staging_password_changed_at = timezone.now()
    site.staging_access_version = uuid.uuid4()
    site.save()
    AuditEvent.objects.create(
        actor=owner,
        action="security.staging_password_rotated",
        record_type="settings",
        record_id="1",
    )
    return site


class AccessForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, label="Staging password")


@sensitive_post_parameters("password")
@require_http_methods(["GET", "POST"])
def staging_access(request):
    form = AccessForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        if not allow_security_request(
            "staging-gate:" + request.META.get("REMOTE_ADDR", "unknown"), 5
        ):
            response = HttpResponse(
                "Please wait before trying the staging password again.", status=429
            )
            response["Retry-After"] = "900"
            return response
        site = SiteSettings.objects.filter(pk=1).first()
        if password_current(site) and check_password(
            form.cleaned_data["password"], site.staging_password_hash
        ):
            return grant_access(redirect("home"), site)
        form.add_error(
            None, "A current staging password is required. Contact the owner if it has expired."
        )
    template = (
        "registration/design_review_access.html"
        if getattr(settings, "DESIGN_REVIEW_ONLY", False)
        else "registration/staging_access.html"
    )
    return render(request, template, {"form": form})


@staff_permission("core.change_sitesettings")
@sensitive_post_parameters("password")
@require_http_methods(["GET", "POST"])
def staging_settings(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    form = AccessForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            site = set_staging_password(owner=request.user, password=form.cleaned_data["password"])
        except forms.ValidationError as exc:
            form.add_error("password", exc)
        else:
            messages.success(
                request, "Staging password updated. Previous access tickets no longer work."
            )
            return grant_access(redirect("staging_settings"), site)
    return render(
        request,
        "core/staging_settings.html",
        {"form": form, "site": SiteSettings.objects.filter(pk=1).first()},
    )
