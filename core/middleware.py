from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden


class StagingAccessMiddleware:
    """Keep test pages behind staff login when configured for hosted staging."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.APP_ENV == "staging" and not request.path.startswith(
            ("/accounts/login/", "/static/")
        ):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not request.user.is_active or not request.user.is_staff:
                return HttpResponseForbidden("Staging access requires an active staff account.")
        response = self.get_response(request)
        response["Cache-Control"] = "private, no-store"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response
