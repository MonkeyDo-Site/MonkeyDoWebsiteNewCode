from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from core import (
    account_views,
    booking_views,
    customer_views,
    dashboard,
    membership_views,
    public_booking_views,
    recurring_views,
    scheduling_views,
    staging_access,
    views,
    website_settings,
)
from core.security import ProtectedLoginView

urlpatterns = [
    path("staff/", ProtectedLoginView.as_view(), name="staff_login"),
    path("staff/website-settings/", website_settings.website_settings, name="website_settings"),
    path("staff/scheduling/weekly/", recurring_views.recurring_settings, name="recurring_settings"),
    path("staff/scheduling/weekly/new/", recurring_views.slot_edit, name="weekly_create"),
    path("staff/scheduling/weekly/<int:pk>/", recurring_views.slot_edit, name="weekly_edit"),
    path("staff/scheduling/horizon/", recurring_views.horizon_settings, name="horizon_settings"),
    path("staff/memberships/", membership_views.drafts, name="membership_drafts"),
    path("staff/memberships/new/", membership_views.draft_create, name="membership_create"),
    path(
        "staff/memberships/pricing/", membership_views.membership_pricing, name="membership_pricing"
    ),
    path("staff/memberships/<int:pk>/", membership_views.draft_detail, name="membership_detail"),
    path("staff/scheduling/", scheduling_views.scheduling, name="scheduling"),
    path("staff/scheduling/new/", scheduling_views.session_edit, name="session_create"),
    path("staff/scheduling/date/", scheduling_views.date_edit, name="date_edit"),
    path("staff/scheduling/<int:pk>/", scheduling_views.session_edit, name="session_edit"),
    path("", views.page, name="home"),
    path("about/", views.page, {"name": "about"}, name="about"),
    path("memberships/", views.page, {"name": "memberships"}, name="memberships"),
    path("clubs-parties/", views.page, {"name": "clubs_parties"}, name="clubs_parties"),
    # Preserve earlier bookmarks; this compatibility page is not in navigation.
    path("memberships-clubs-parties/", views.page, {"name": "programs"}, name="programs"),
    path("contact/", views.page, {"name": "contact"}, name="contact"),
    path("book/", views.schedule, name="schedule"),
    path("book/start/<int:session_id>/", public_booking_views.start, name="customer_booking_start"),
    path("book/details/", public_booking_views.wizard, name="customer_booking"),
    path("book/receipt/", public_booking_views.receipt, name="customer_booking_receipt"),
    path("book/revise/", public_booking_views.revise, name="customer_booking_revise"),
    path("staff/bookings/", booking_views.bookings, name="bookings"),
    path("staff/bookings/new/", booking_views.booking_create, name="booking_create"),
    path("staff/bookings/<int:pk>/", booking_views.booking_detail, name="booking_detail"),
    path("staff/bookings/<int:pk>/edit/", booking_views.booking_edit, name="booking_edit"),
    path("staff/bookings/<int:pk>/timing/", booking_views.booking_move, name="booking_move"),
    path("staff/bookings/<int:pk>/release/", booking_views.booking_release, name="booking_release"),
    path("staff/pricing/", booking_views.pricing_settings, name="pricing_settings"),
    path("staff/today/", views.today, name="today"),
    path("accounts/login/", ProtectedLoginView.as_view(), name="login"),
    path("accounts/owner/verify/", account_views.verify_owner, name="owner_verify"),
    path("accounts/owner/resend/", account_views.resend_owner, name="owner_resend"),
    path(
        "accounts/password-reset/",
        account_views.ProtectedPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "accounts/password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        account_views.ProtectedPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("staging/access/", staging_access.staging_access, name="staging_access"),
    path("staff/staging-access/", staging_access.staging_settings, name="staging_settings"),
    path("staff/accounts/", account_views.staff_accounts, name="staff_accounts"),
    path("staff/accounts/<int:pk>/", account_views.staff_accounts, name="staff_account_edit"),
    path("staff/owner-security/", account_views.owner_security, name="owner_security"),
    path("staff/owner-security/codes/", account_views.recovery_codes, name="recovery_codes"),
    path("accounts/revoke-sessions/", account_views.revoke_sessions, name="revoke_sessions"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Do not leave the inspector with an unthrottled second password endpoint.
    path("admin/login/", RedirectView.as_view(pattern_name="login", query_string=True)),
    path("admin/", admin.site.urls),
    path("staff/customers/", customer_views.customer_list, name="customers"),
    path("staff/customers/new/", customer_views.customer_create, name="customer_create"),
    path("staff/customers/<int:pk>/", customer_views.customer_detail, name="customer_detail"),
    path("staff/customers/<int:pk>/edit/", customer_views.customer_edit, name="customer_edit"),
    path(
        "staff/customers/<int:pk>/previous-phone/",
        customer_views.previous_phone,
        name="previous_phone",
    ),
    path("staff/customers/<int:pk>/comments/new/", customer_views.comment_edit, name="comment_add"),
    path(
        "staff/customers/<int:pk>/comments/<int:comment_id>/",
        customer_views.comment_edit,
        name="comment_edit",
    ),
    path(
        "staff/customers/<int:pk>/history/",
        customer_views.customer_history,
        name="customer_history",
    ),
    path("staff/dashboard/", dashboard.dashboard, name="dashboard"),
    path("staff/security-alerts/<int:pk>/resolve/", dashboard.resolve_alert, name="resolve_alert"),
    path("health/", views.health, name="health"),
]
