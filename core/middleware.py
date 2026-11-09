import ipaddress

from django.conf import settings


class StagingAccessMiddleware:
    """Keep test pages behind staff login when configured for hosted staging."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.APP_ENV == "staging":
            from django.shortcuts import redirect

            from .models import SiteSettings
            from .staging_access import access_valid

            public_auth = (
                "/accounts/login/",
                "/accounts/logout/",
                "/accounts/revoke-sessions/",
                "/accounts/owner/verify/",
                "/accounts/owner/resend/",
                "/accounts/password-reset/",
                "/accounts/reset/",
                "/staging/access/",
                "/static/",
            )
            owner_setup = (
                request.path == "/staff/staging-access/"
                and request.user.is_authenticated
                and request.user.is_superuser
            )
            if (
                request.path != "/staff/"
                and not request.path.startswith(public_auth)
                and not owner_setup
            ):
                if not access_valid(request, SiteSettings.objects.filter(pk=1).first()):
                    response = redirect("staging_access")
                    response["Cache-Control"] = "private, no-store"
                    response["X-Robots-Tag"] = "noindex, nofollow"
                    return response
        response = self.get_response(request)
        response["Cache-Control"] = "private, no-store"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response


class AccountAccessMiddleware:
    """Enforce fresh account privileges, 12-hour inactivity and owner verification."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.contrib.auth import logout
        from django.shortcuts import redirect
        from django.utils import timezone

        from .models import AccountSecurity

        if request.user.is_authenticated:
            profile, _ = AccountSecurity.objects.get_or_create(user=request.user)
            now = timezone.now().timestamp()
            last = request.session.get("last_activity")
            stale = request.session.get("account_version") != profile.version
            stale = stale or (last is not None and now - last >= 12 * 60 * 60)
            if request.user.is_superuser:
                verified = request.session.get("owner_verified_at")
                stale = (
                    stale
                    or request.session.get("owner_mfa_version") != profile.version
                    or verified is None
                    or now - verified >= 30 * 24 * 60 * 60
                )
            if stale:
                logout(request)
                if not request.path.startswith("/accounts/"):
                    return redirect("login")
            else:
                request.session["last_activity"] = now
        return self.get_response(request)


class LocalProxyClientIPMiddleware:
    """Only the opt-in private local nginx connection may supply X-Real-IP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.TRUST_LOCAL_CLIENT_IP and request.META.get("REMOTE_ADDR", "") in {
            "",
            "127.0.0.1",
            "::1",
        }:
            try:
                address = ipaddress.ip_address(request.META.get("HTTP_X_REAL_IP", ""))
            except ValueError:
                pass
            else:
                request.META["REMOTE_ADDR"] = str(address)
        return self.get_response(request)
