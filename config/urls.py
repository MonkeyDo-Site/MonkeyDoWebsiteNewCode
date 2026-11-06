from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from core import account_views, customer_views, dashboard, staging_access, views
from core.security import ProtectedLoginView

urlpatterns = [
    path("", views.page, name="home"),
    path("about/", views.page, {"name": "about"}, name="about"),
    path("memberships-clubs-parties/", views.page, {"name": "programs"}, name="programs"),
    path("contact/", views.page, {"name": "contact"}, name="contact"),
    path("book/", views.schedule, name="schedule"),
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
