from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    INTERNAL_RESET_SESSION_TOKEN,
    PasswordResetConfirmView,
    PasswordResetView,
)
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST

from .account_forms import (
    OwnerCodeForm,
    RecoveryEmailForm,
    StaffAccountForm,
    StaffPasswordResetForm,
)
from .account_management import save_staff_account
from .account_security import (
    TRUST_COOKIE,
    allow_security_request,
    resend_owner_challenge,
    rotate_recovery_codes,
    verify_owner_challenge,
)
from .models import AccountSecurity, AuditEvent, OwnerChallenge
from .permissions import staff_permission
from .tokens import account_reset_token


def pending_challenge(request):
    value = request.session.get("owner_challenge")
    try:
        return OwnerChallenge.objects.get(pk=value) if value else None
    except (OwnerChallenge.DoesNotExist, ValidationError, ValueError):
        return None


@sensitive_post_parameters("code")
@require_http_methods(["GET", "POST"])
def verify_owner(request):
    challenge = pending_challenge(request)
    if not challenge:
        return redirect("login")
    form = OwnerCodeForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        verified = verify_owner_challenge(challenge.pk, form.cleaned_data["code"])
        if verified:
            user, token, version = verified
            target = request.session.pop("owner_next", reverse_lazy("today"))
            request.session.pop("owner_challenge", None)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            request.session["owner_verified_at"] = timezone.now().timestamp()
            request.session["owner_mfa_version"] = version
            response = redirect(target)
            response.set_cookie(
                TRUST_COOKIE,
                token,
                max_age=30 * 24 * 60 * 60,
                httponly=True,
                secure=settings.APP_ENV == "staging",
                samesite="Lax",
            )
            return response
        form.add_error(
            None,
            "That code is invalid, expired, or already used. After five failed attempts, sign in again.",
        )
    return render(
        request,
        "registration/owner_verify.html",
        {
            "form": form,
            "secondary_available": bool(challenge.user.account_security.secondary_email),
            "delivered": challenge.delivered,
            "test_email_backend": settings.EMAIL_BACKEND
            == "django.core.mail.backends.locmem.EmailBackend",
        },
    )


@require_POST
def resend_owner(request):
    challenge = pending_challenge(request)
    if not challenge:
        return redirect("login")
    try:
        resend_owner_challenge(
            challenge.pk, secondary=request.POST.get("destination") == "secondary"
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("owner_verify")


@staff_permission("auth.change_user")
@require_http_methods(["GET", "POST"])
def owner_security(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    profile = AccountSecurity.objects.get(user=request.user)
    form = RecoveryEmailForm(
        request.POST if request.method == "POST" else None,
        initial={"secondary_email": profile.secondary_email},
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            profile = AccountSecurity.objects.select_for_update().get(user=request.user)
            before = profile.secondary_email
            profile.secondary_email = form.cleaned_data["secondary_email"]
            profile.version += 1
            profile.save()
            request.session["account_version"] = profile.version
            request.session["owner_mfa_version"] = profile.version
            AuditEvent.objects.create(
                actor=request.user,
                action="security.recovery_email_updated",
                record_type="account",
                record_id=str(request.user.pk),
                changes={"before": before, "after": profile.secondary_email},
            )
        messages.success(request, "Recovery email saved.")
        return redirect("owner_security")
    return render(request, "core/owner_security.html", {"form": form})


@staff_permission("auth.change_user")
@sensitive_variables("codes")
@require_POST
def recovery_codes(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    codes = rotate_recovery_codes(request.user)
    # Codes are returned once in this no-store response, never in session, audit or URL.
    return render(request, "core/recovery_codes.html", {"codes": codes})


@login_required
@require_POST
def revoke_sessions(request):
    with transaction.atomic():
        profile = AccountSecurity.objects.select_for_update().get(user=request.user)
        profile.version += 1
        profile.save()
        AuditEvent.objects.create(
            actor=request.user,
            action="security.sessions_revoked",
            record_type="account",
            record_id=str(request.user.pk),
        )
    logout(request)
    response = redirect("login")
    response.delete_cookie(TRUST_COOKIE)
    return response


@staff_permission("auth.change_user")
@sensitive_post_parameters("password")
@require_http_methods(["GET", "POST"])
def staff_accounts(request, pk=None):
    if not request.user.is_superuser:
        raise PermissionDenied
    User = get_user_model()
    user = get_object_or_404(User, pk=pk, is_superuser=False, is_staff=True) if pk else None
    form = StaffAccountForm(request.POST if request.method == "POST" else None, user=user)
    if request.method == "POST" and form.is_valid():
        try:
            save_staff_account(owner=request.user, user_id=pk, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            messages.success(
                request, "Staff account saved. Existing sessions have been invalidated."
            )
            return redirect("staff_accounts")
    return render(
        request,
        "core/staff_accounts.html",
        {
            "form": form,
            "editing": user,
            "accounts": User.objects.filter(is_staff=True, is_superuser=False).order_by("username"),
        },
    )


class ProtectedPasswordResetView(PasswordResetView):
    token_generator = account_reset_token
    form_class = StaffPasswordResetForm
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")

    def form_valid(self, form):
        if not allow_security_request(
            "password-reset-email:" + form.cleaned_data["email"].casefold(), 3
        ):
            return redirect("password_reset_done")
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        if not allow_security_request(
            "password-reset:" + request.META.get("REMOTE_ADDR", "unknown"), 5
        ):
            response = HttpResponse("Please wait before requesting another reset link.", status=429)
            response["Retry-After"] = "900"
            return response
        return super().post(request, *args, **kwargs)


class ProtectedPasswordResetConfirmView(PasswordResetConfirmView):
    token_generator = account_reset_token
    template_name = "registration/password_reset_confirm.html"

    @transaction.atomic
    def form_valid(self, form):
        # Recheck after locking: two browsers must not both redeem the same reset.
        user = get_user_model().objects.select_for_update().get(pk=self.user.pk)
        token = self.request.session.get(INTERNAL_RESET_SESSION_TOKEN, "")
        if not self.token_generator.check_token(user, token):
            self.request.session.pop(INTERNAL_RESET_SESSION_TOKEN, None)
            self.validlink = False
            return self.render_to_response(self.get_context_data())
        form.user = user
        self.user = user
        response = super().form_valid(form)
        AuditEvent.objects.create(
            action="security.password_reset",
            record_type="account",
            record_id=str(user.pk),
            changes={"method": "emailed_reset_link"},
        )
        return response
