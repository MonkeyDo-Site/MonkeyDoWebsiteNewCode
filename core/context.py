from django.conf import settings


def site_context(request):
    return {
        "test_mode": True,
        "customer_test_booking": settings.CUSTOMER_TEST_BOOKING and not settings.DESIGN_REVIEW_ONLY,
    }
