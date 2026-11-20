from django.conf import settings

from .models import SiteSettings


def site_context(request):
    site = SiteSettings.objects.only("clubs_visible").filter(pk=1).first()
    name = request.resolver_match.url_name if request.resolver_match else ""
    parent = None
    if name.startswith("booking_"):
        parent = ("Bookings", "/staff/bookings/")
    elif name.startswith("customer_") or name in {"previous_phone", "comment_add", "comment_edit"}:
        parent = ("Customers", "/staff/customers/")
    elif name.startswith("membership_") and name != "membership_drafts":
        parent = ("Membership drafts", "/staff/memberships/")
    return {
        "staff_parent": parent,
        "payment_sandbox_enabled": settings.PAYMENT_SANDBOX_ENABLED,
        "waiver_enabled": settings.WAIVER_ENABLED,
        "booking_email_enabled": settings.BOOKING_EMAIL_ENABLED,
        "owner_scheduling_section": bool(
            request.resolver_match
            and request.resolver_match.url_name
            in {
                "scheduling",
                "session_create",
                "session_edit",
                "date_edit",
                "recurring_settings",
                "weekly_batch_edit",
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
