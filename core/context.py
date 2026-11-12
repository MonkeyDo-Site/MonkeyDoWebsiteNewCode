from django.conf import settings

from .models import SiteSettings


def site_context(request):
    site = SiteSettings.objects.only("clubs_visible").filter(pk=1).first()
    return {
        "owner_scheduling_section": bool(
            request.resolver_match
            and request.resolver_match.url_name
            in {
                "scheduling",
                "session_create",
                "session_edit",
                "date_edit",
                "recurring_settings",
                "weekly_create",
                "weekly_edit",
                "weekly_delete",
                "horizon_settings",
            }
        ),
        "clubs_visible": site.clubs_visible if site else False,
        "test_mode": True,
        "customer_test_booking": settings.CUSTOMER_TEST_BOOKING and not settings.DESIGN_REVIEW_ONLY,
    }
