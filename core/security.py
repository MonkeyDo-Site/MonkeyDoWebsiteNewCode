"""Database-backed, temporary login delays; no permanent account lockout."""

import math
import unicodedata
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .forms import StaffAuthenticationForm
from .models import AuditEvent, LoginThrottle, SecurityAlert


class ProtectedLoginView(LoginView):
    authentication_form = StaffAuthenticationForm

    def blocked_response(self, request, seconds):
        # An empty password avoids running credential verification on a blocked request.
        form = self.authentication_form(
            request=request, data={"username": request.POST.get("username", "")}
        )
        form.add_error(None, "Too many sign-in attempts. Please wait briefly and try again.")
        response = self.form_invalid(form)
        response.status_code = 429
        response["Retry-After"] = str(max(1, seconds))
        return response

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        # Do not trust forwarded IP headers before the origin/proxy trust is configured.
        canonical_username = unicodedata.normalize("NFKC", request.POST.get("username", "").strip())
        identifiers = {
            "account": canonical_username.casefold(),
            "network": request.META.get("REMOTE_ADDR", "unknown"),
        }
        keys = {
            scope: scope
            + ":"
            + salted_hmac("login-throttle", value, algorithm="sha256").hexdigest()
            for scope, value in identifiers.items()
        }
        network = LoginThrottle.objects.filter(key=keys["network"]).first()
        now = timezone.now()
        if network and network.blocked_until and network.blocked_until > now:
            return self.blocked_response(
                request, math.ceil((network.blocked_until - now).total_seconds())
            )
        for key in sorted(keys.values()):
            LoginThrottle.objects.get_or_create(key=key)
        states = list(
            LoginThrottle.objects.select_for_update().filter(key__in=keys.values()).order_by("key")
        )
        now = timezone.now()
        for state in states:
            if state.last_failure and now - state.last_failure >= timedelta(minutes=15):
                state.failures = 0
                state.blocked_until = None
        waits = [
            math.ceil((state.blocked_until - now).total_seconds())
            for state in states
            if state.blocked_until and state.blocked_until > now
        ]
        if waits:
            return self.blocked_response(request, max(waits))
        response = super().post(request, *args, **kwargs)
        if response.status_code == 302:
            account = next(state for state in states if state.key == keys["account"])
            account.failures = 0
            account.blocked_until = None
            account.last_failure = None
            account.save()
            return response
        for state in states:
            scope = state.key.split(":", 1)[0]
            threshold = 5 if scope == "account" else 25
            state.failures += 1
            state.last_failure = now
            state.blocked_until = (
                (now + timedelta(seconds=min(300, 2 ** min(9, state.failures - threshold))))
                if state.failures >= threshold
                else None
            )
            state.save()
            if state.failures == threshold * 2:
                known_username = None
                if scope == "account":
                    known_username = (
                        get_user_model()
                        .objects.filter(username=canonical_username)
                        .values_list("username", flat=True)
                        .first()
                    )
                alert = SecurityAlert.objects.create(
                    subject="Repeated failed sign-in attempts",
                    details={
                        "scope": scope,
                        "bucket": state.key,
                        "attempts": state.failures,
                        "account_username": known_username,
                    },
                )
                AuditEvent.objects.create(
                    action="security.login_alert",
                    record_type="security_alert",
                    record_id=str(alert.pk),
                    changes={"scope": scope, "attempts": state.failures},
                )
        return response
