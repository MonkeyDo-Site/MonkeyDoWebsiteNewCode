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
from core.backups import views as backup_views
from core.communications import views as message_views
from core.communications.webhooks import endpoint as email_webhook
from core.payments import staff_setup
from core.payments import views as payment_views
from core.payments.checkout_views import checkout as booking_checkout
from core.payments.checkout_views import complimentary, remaining_payment
from core.payments.setup_views import setup_card, setup_status
from core.payments.views import payment_correction
from core.payments.webhooks import endpoint as payment_webhook
from core.security import ProtectedLoginView
from core.waivers import views as waiver_views

urlpatterns = [
    path("staff/backups/<uuid:pk>/review/", backup_views.review_issue, name="backup_review_issue"),
    path("staff/background/<uuid:pk>/", payment_views.background_job, name="background_job"),
    path("staff/cards/<uuid:pk>/retire/", payment_views.retire_card, name="retire_card"),
    path(
        "staff/cards/<uuid:pk>/removal/", payment_views.removal_review, name="card_removal_review"
    ),
    path("integrations/resend/webhook/", email_webhook, name="email_webhook"),
    path(
        "book/complete/email/", public_booking_views.completion_email, name="customer_booking_email"
    ),
    path("staff/backups/", backup_views.backups, name="backups"),
    path("staff/backups/<uuid:pk>/download/", backup_views.download, name="backup_download"),
    path(
        "staff/backups/<uuid:pk>/manifest/",
        backup_views.download,
        {"metadata": True},
        name="backup_manifest",
    ),
    path(
        "staff/backups/<uuid:pk>/restore-check/", backup_views.record_restore, name="backup_restore"
    ),
    path("staff/payments/<uuid:pk>/correction/", payment_correction, name="payment_correction"),
    path(
        "staff/bookings/<int:pk>/card/change/", staff_setup.replace_card, name="booking_card_change"
    ),
    path("staff/bookings/<int:pk>/complimentary/", complimentary, name="booking_comped"),
    path(
        "staff/bookings/<int:pk>/payment/retry/",
        remaining_payment,
        {"retry": True},
        name="booking_retry_card",
    ),
    path("staff/bookings/<int:pk>/payment/", remaining_payment, name="booking_payment"),
    path("staff/bookings/<int:pk>/arrival/", booking_checkout, name="booking_arrival"),
    path(
        "staff/bookings/<int:pk>/cancel/",
        booking_checkout,
        {"kind": "cancellation"},
        name="booking_cancel",
    ),
    path(
        "staff/bookings/<int:pk>/no-show/",
        booking_checkout,
        {"kind": "no_show"},
        name="booking_no_show",
    ),
    path(
        "staff/bookings/<int:pk>/setup/",
        staff_setup.staff_booking_setup,
        name="staff_booking_setup",
    ),
    path(
        "staff/bookings/<int:pk>/card/setup/", staff_setup.staff_card_setup, name="staff_card_setup"
    ),
    path(
        "staff/bookings/<int:pk>/card/setup/<uuid:setup_id>/",
        staff_setup.staff_card_status,
        name="staff_card_status",
    ),
    path("staff/messages/", message_views.message_list, name="messages"),
    path(
        "staff/bookings/<int:booking_id>/waiver/paper/",
        waiver_views.paper_review,
        name="waiver_paper_review",
    ),
    path("staff/messages/<uuid:pk>/", message_views.message_detail, name="message_detail"),
    path("waiver/unsigned.pdf", waiver_views.unsigned_pdf, name="unsigned_waiver"),
    path("waiver/shared/<str:token>/", waiver_views.shared_sign, name="shared_waiver"),
    path(
        "book/payment-method/", public_booking_views.payment_method, name="customer_payment_method"
    ),
    path("book/waiver/complete/", waiver_views.public_complete, name="customer_waiver_complete"),
    path("book/waiver/", waiver_views.public_sign, name="customer_waiver"),
    path("staff/waivers/", waiver_views.waivers, name="waivers"),
    path("staff/waivers/<uuid:pk>/", waiver_views.waiver_detail, name="waiver_detail"),
    path("staff/waivers/<uuid:pk>/evidence/", waiver_views.evidence, name="waiver_evidence"),
    path(
        "staff/bookings/<int:booking_id>/waiver/share/",
        waiver_views.share_create,
        name="waiver_share_create",
    ),
    path("staff/payments/", payment_views.payments, name="payments"),
    path("staff/payments/<uuid:pk>/", payment_views.payment_detail, name="payment_detail"),
    path("staff/card-setups/<uuid:pk>/", payment_views.card_setup_detail, name="card_setup_detail"),
    path("book/card/setup/", setup_card, name="customer_card_setup"),
    path("book/card/setup/<uuid:setup_id>/", setup_status, name="customer_card_status"),
    path("integrations/banquest/webhook/", payment_webhook, name="banquest_webhook"),
    path("staff/", ProtectedLoginView.as_view(), name="staff_login"),
    path("staff/website-settings/", website_settings.website_settings, name="website_settings"),
    path("staff/scheduling/weekly/", recurring_views.recurring_settings, name="recurring_settings"),
    path(
        "staff/scheduling/weekly/edit-all/", recurring_views.schedule_edit, name="weekly_batch_edit"
    ),
    path("staff/scheduling/weekly/new/", recurring_views.slot_edit, name="weekly_create"),
    path("staff/scheduling/weekly/<int:pk>/", recurring_views.slot_edit, name="weekly_edit"),
    path(
        "staff/scheduling/weekly/<int:pk>/delete/",
        recurring_views.slot_delete,
        name="weekly_delete",
    ),
    path("staff/scheduling/horizon/", recurring_views.horizon_settings, name="horizon_settings"),
    path("staff/memberships/", membership_views.drafts, name="membership_drafts"),
    path("staff/memberships/new/", membership_views.draft_create, name="membership_create"),
    path(
        "staff/memberships/pricing/", membership_views.membership_pricing, name="membership_pricing"
    ),
    path("staff/memberships/<int:pk>/edit/", membership_views.draft_edit, name="membership_edit"),
    path("staff/memberships/<int:pk>/", membership_views.draft_detail, name="membership_detail"),
    path("staff/scheduling/", scheduling_views.scheduling, name="scheduling"),
    path("staff/scheduling/new/", scheduling_views.session_edit, name="session_create"),
    path("staff/scheduling/date/", scheduling_views.date_edit, name="date_edit"),
    path(
        "staff/scheduling/<int:pk>/reopen/",
        scheduling_views.reopen_custom_session,
        name="session_reopen",
    ),
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
    path("book/recover/", public_booking_views.recover_by_email, name="customer_email_recovery"),
    path("book/estimate/", public_booking_views.live_estimate, name="customer_live_estimate"),
    path("book/details/", public_booking_views.wizard, name="customer_booking"),
    path("book/receipt/", public_booking_views.receipt, name="customer_booking_receipt"),
    path("book/revise/", public_booking_views.revise, name="customer_booking_revise"),
    path("staff/bookings/", booking_views.bookings, name="bookings"),
    path("staff/bookings/sessions/", booking_views.dated_sessions, name="dated_sessions"),
    path("staff/bookings/new/", booking_views.booking_create, name="booking_create"),
    path("staff/bookings/<int:pk>/", booking_views.booking_detail, name="booking_detail"),
    path(
        "staff/bookings/<int:pk>/estimate/", booking_views.booking_estimate, name="booking_estimate"
    ),
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
    path("staff/customers/search/", customer_views.customer_choices, name="customer_choices"),
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
    path("staff/notices/<int:pk>/review/", dashboard.review_notice, name="review_notice"),
    path("staff/dashboard/", dashboard.dashboard, name="dashboard"),
    path("staff/security-alerts/<int:pk>/resolve/", dashboard.resolve_alert, name="resolve_alert"),
    path("health/", views.health, name="health"),
]
