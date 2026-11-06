import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.account_management import save_staff_account
from core.account_security import (
    TRUST_COOKIE,
    resend_owner_challenge,
    rotate_recovery_codes,
    start_owner_challenge,
    trusted_browser,
    verify_owner_challenge,
)
from core.models import (
    AccountSecurity,
    AuditEvent,
    OwnerChallenge,
    OwnerRecoveryCode,
    TrustedOwnerBrowser,
)
from tests.helpers import verified_owner_login

PASSWORD = "Artificial-Owner-Password-9381!"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=STORAGES)
class OwnerMFATests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="owner",
            email="owner@example.invalid",
            password=PASSWORD,
            is_staff=True,
            is_superuser=True,
        )

    def password_step(self, client=None):
        return (client or self.client).post(
            "/accounts/login/", {"username": "owner", "password": PASSWORD}
        )

    def email_code(self):
        return re.search(r"code is ([0-9]{6})", mail.outbox[-1].body).group(1)

    def verified_login(self):
        self.password_step()
        response = self.client.post("/accounts/owner/verify/", {"code": self.email_code()})
        self.assertEqual(response.status_code, 302)
        return response

    def test_password_alone_does_not_create_privileged_session(self):
        self.assertEqual(self.password_step().url, "/accounts/owner/verify/")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get("/staff/accounts/").status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        challenge = OwnerChallenge.objects.get()
        self.assertFalse(challenge.digest == self.email_code())

    def test_valid_code_authenticates_and_cookie_is_http_only(self):
        response = self.verified_login()
        self.assertIn("_auth_user_id", self.client.session)
        self.assertTrue(response.cookies[TRUST_COOKIE]["httponly"])
        self.assertEqual(self.client.get("/staff/accounts/").status_code, 200)
        self.assertEqual(TrustedOwnerBrowser.objects.count(), 1)

    def test_code_is_single_use(self):
        self.password_step()
        challenge = OwnerChallenge.objects.get()
        code = self.email_code()
        self.assertIsNotNone(verify_owner_challenge(challenge.pk, code))
        self.assertIsNone(verify_owner_challenge(challenge.pk, code))

    def test_expired_code_never_authenticates(self):
        self.password_step()
        challenge = OwnerChallenge.objects.get()
        with patch("core.account_security.timezone.now", return_value=challenge.expires_at):
            self.assertIsNone(verify_owner_challenge(challenge.pk, self.email_code()))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_five_wrong_codes_consume_challenge(self):
        self.password_step()
        challenge = OwnerChallenge.objects.get()
        valid = self.email_code()
        wrong = "111111" if valid != "111111" else "222222"
        for _ in range(5):
            self.assertIsNone(verify_owner_challenge(challenge.pk, wrong))
        self.assertIsNone(verify_owner_challenge(challenge.pk, valid))
        challenge.refresh_from_db()
        self.assertEqual(challenge.attempts, 5)
        self.assertIsNotNone(challenge.consumed_at)

    def test_trusted_browser_skips_code_until_original_thirty_day_expiry(self):
        response = self.verified_login()
        token = response.cookies[TRUST_COOKIE].value
        browser = TrustedOwnerBrowser.objects.get()
        self.client.post("/accounts/logout/")
        sent = len(mail.outbox)
        with patch(
            "django.utils.timezone.now", return_value=browser.expires_at - timedelta(days=1)
        ):
            self.assertEqual(self.password_step().url, "/staff/today/")
        self.assertEqual(len(mail.outbox), sent)
        self.assertTrue(trusted_browser(self.owner, token))
        # Repeated password sign-ins must not extend the 30-day verification.
        with patch("django.utils.timezone.now", return_value=browser.expires_at):
            self.assertEqual(self.client.get("/staff/accounts/").status_code, 302)
            self.assertFalse(trusted_browser(self.owner, token))

    def test_password_reset_or_privilege_change_invalidates_pending_code(self):
        self.password_step()
        challenge = OwnerChallenge.objects.get()
        code = self.email_code()
        self.owner.set_password("Changed-Artificial-Password-839!")
        self.owner.save()
        self.assertIsNone(verify_owner_challenge(challenge.pk, code))

    def test_recovery_code_single_use_and_rotation_replaces_old_set(self):
        codes = rotate_recovery_codes(self.owner)
        self.assertEqual(len(codes), 10)
        challenge = start_owner_challenge(self.owner)
        self.assertIsNotNone(verify_owner_challenge(challenge.pk, codes[0]))
        second = start_owner_challenge(self.owner)
        self.assertIsNone(verify_owner_challenge(second.pk, codes[0]))
        rotate_recovery_codes(self.owner)
        self.assertIsNone(verify_owner_challenge(second.pk, codes[1]))
        self.assertFalse(OwnerRecoveryCode.objects.filter(digest__in=codes).exists())
        self.assertFalse(
            any(
                code in str(list(AuditEvent.objects.values_list("changes", flat=True)))
                for code in codes
            )
        )

    def test_secondary_resend_uses_only_configured_address_and_old_code_expires(self):
        profile = AccountSecurity.objects.get(user=self.owner)
        profile.secondary_email = "secondary@example.invalid"
        profile.save()
        challenge = start_owner_challenge(self.owner)
        original = self.email_code()
        with patch(
            "core.account_security.timezone.now",
            return_value=challenge.last_sent_at + timedelta(seconds=61),
        ):
            resend_owner_challenge(challenge.pk, secondary=True)
        self.assertEqual(mail.outbox[-1].to, ["secondary@example.invalid"])
        self.assertIsNone(verify_owner_challenge(challenge.pk, original))
        self.assertIsNotNone(verify_owner_challenge(challenge.pk, self.email_code()))

    def test_resend_rate_limited_and_attempts_not_reset(self):
        challenge = start_owner_challenge(self.owner)
        with self.assertRaises(ValidationError):
            resend_owner_challenge(challenge.pk)
        verify_owner_challenge(challenge.pk, "not-a-code")
        with patch(
            "core.account_security.timezone.now",
            return_value=challenge.last_sent_at + timedelta(seconds=61),
        ):
            resend_owner_challenge(challenge.pk)
        challenge.refresh_from_db()
        self.assertEqual(challenge.attempts, 1)

    def test_missing_owner_email_fails_closed(self):
        self.owner.email = ""
        self.owner.save()
        response = self.password_step()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(OwnerChallenge.objects.exists())

    def test_privileged_force_login_without_mfa_is_rejected(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_owner_codes_are_post_only_and_not_retrievable_on_get(self):
        verified_owner_login(self.client, self.owner)
        self.assertEqual(self.client.get("/staff/owner-security/codes/").status_code, 405)
        response = self.client.post("/staff/owner-security/codes/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["codes"]), 10)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn("codes", self.client.session)

    def test_recovery_email_change_revokes_other_sessions(self):
        other = Client()
        verified_owner_login(other, self.owner)
        verified_owner_login(self.client, self.owner)
        self.assertEqual(
            self.client.post(
                "/staff/owner-security/", {"secondary_email": "new-secondary@example.invalid"}
            ).status_code,
            302,
        )
        self.assertEqual(other.get("/staff/accounts/").status_code, 302)
        self.assertEqual(self.client.get("/staff/accounts/").status_code, 200)

    @override_settings(APP_ENV="staging", SECURE_SSL_REDIRECT=False)
    def test_staging_gate_allows_verification_and_password_reset_but_not_settings(self):
        self.assertEqual(self.client.get("/accounts/password-reset/", secure=True).status_code, 200)
        self.assertEqual(self.client.get("/staff/owner-security/", secure=True).status_code, 302)
        response = self.client.post(
            "/accounts/login/", {"username": "owner", "password": PASSWORD}, secure=True
        )
        self.assertEqual(response.url, "/accounts/owner/verify/")
        self.assertEqual(self.client.get("/accounts/owner/verify/", secure=True).status_code, 200)
        response = self.client.post(
            "/accounts/owner/verify/", {"code": self.email_code()}, secure=True
        )
        self.assertTrue(response.cookies[TRUST_COOKIE]["secure"])


@override_settings(STORAGES=STORAGES)
class StaffAccountTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="owner",
            email="owner@example.invalid",
            password=PASSWORD,
            is_staff=True,
            is_superuser=True,
        )
        self.staff = get_user_model().objects.create_user(
            username="staff", email="staff@example.invalid", password=PASSWORD, is_staff=True
        )
        self.permission = Permission.objects.get(
            content_type__app_label="core", codename="view_customer"
        )
        self.staff.user_permissions.add(self.permission)

    def test_staff_has_no_mfa_but_permissions_removal_ends_session(self):
        response = self.client.post("/accounts/login/", {"username": "staff", "password": PASSWORD})
        self.assertEqual(response.url, "/staff/today/")
        self.assertFalse(OwnerChallenge.objects.exists())
        self.assertEqual(self.client.get("/staff/customers/").status_code, 200)
        self.staff.user_permissions.clear()
        self.assertEqual(self.client.get("/staff/customers/").status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_group_permission_removal_ends_session(self):
        self.staff.user_permissions.clear()
        group = Group.objects.create(name="Scoped staff")
        group.permissions.add(self.permission)
        self.staff.groups.add(group)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/staff/customers/").status_code, 200)
        group.permissions.clear()
        self.assertEqual(self.client.get("/staff/customers/").status_code, 302)

    def test_inactivity_logs_out_but_active_use_refreshes_window(self):
        self.client.force_login(self.staff)
        now = timezone.now()
        session = self.client.session
        session["last_activity"] = now.timestamp()
        session.save()
        with patch("django.utils.timezone.now", return_value=now + timedelta(hours=11)):
            self.assertEqual(self.client.get("/staff/customers/").status_code, 200)
        with patch("django.utils.timezone.now", return_value=now + timedelta(hours=13)):
            self.assertEqual(self.client.get("/staff/customers/").status_code, 200)
        with patch("django.utils.timezone.now", return_value=now + timedelta(hours=25)):
            self.assertEqual(self.client.get("/staff/customers/").status_code, 302)

    def test_owner_can_create_update_disable_and_reset_staff_without_secrets_in_audit(self):
        user = save_staff_account(
            owner=self.owner,
            username="new-staff",
            email="new@example.invalid",
            password=PASSWORD,
            permissions=[self.permission],
        )
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_superuser)
        self.client.force_login(user)
        profile = AccountSecurity.objects.get(user=user)
        save_staff_account(
            owner=self.owner,
            user_id=user.pk,
            version=profile.version,
            email=user.email,
            is_active=False,
            permissions=[],
        )
        self.assertEqual(self.client.get("/staff/customers/").status_code, 302)
        self.assertFalse(any(PASSWORD in str(event.changes) for event in AuditEvent.objects.all()))

    def test_staff_cannot_manage_accounts_or_generate_owner_recovery(self):
        self.client.force_login(self.staff)
        for path in ("/staff/accounts/", "/staff/owner-security/"):
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post("/staff/owner-security/codes/").status_code, 403)
        with self.assertRaises(PermissionDenied):
            save_staff_account(
                owner=self.staff,
                username="forbidden",
                email="bad@example.invalid",
                password=PASSWORD,
            )

    def test_short_password_and_owner_permission_grants_rejected(self):
        with self.assertRaises(ValidationError):
            save_staff_account(
                owner=self.owner,
                username="new-staff",
                email="new@example.invalid",
                password="short",
            )
        forbidden = Permission.objects.get(content_type__app_label="auth", codename="change_user")
        with self.assertRaises(ValidationError):
            save_staff_account(
                owner=self.owner,
                username="new-staff",
                email="new@example.invalid",
                password=PASSWORD,
                permissions=[forbidden],
            )

    def test_stale_staff_edit_rejected(self):
        profile = AccountSecurity.objects.get(user=self.staff)
        with self.assertRaises(ValidationError):
            save_staff_account(
                owner=self.owner,
                user_id=self.staff.pk,
                version=profile.version - 1,
                email=self.staff.email,
            )

    def test_owner_cannot_be_disabled_from_staff_screen(self):
        with self.assertRaises(ValidationError):
            save_staff_account(
                owner=self.owner,
                user_id=self.owner.pk,
                version=1,
                email=self.owner.email,
                is_active=False,
            )

    def test_single_owner_and_case_insensitive_username_database_guards(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create_user(
                username="second-owner", is_superuser=True, is_staff=True
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create_user(username="STAFF")

    def test_username_immutable_and_account_cannot_be_deleted(self):
        with self.assertRaises(DatabaseError), transaction.atomic():
            get_user_model().objects.filter(pk=self.staff.pk).update(username="replacement")
        with self.assertRaises(ProtectedError):
            self.staff.delete()

    def test_disabled_username_cannot_be_reused(self):
        self.staff.is_active = False
        self.staff.save()
        with self.assertRaises(ValidationError):
            save_staff_account(
                owner=self.owner, username="staff", email="new@example.invalid", password=PASSWORD
            )

    def test_staff_form_roundtrip_and_password_never_displays(self):
        verified_owner_login(self.client, self.owner)
        response = self.client.get(f"/staff/accounts/{self.staff.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.staff.password)
        version = AccountSecurity.objects.get(user=self.staff).version
        response = self.client.post(
            f"/staff/accounts/{self.staff.pk}/",
            {
                "email": "updated@example.invalid",
                "is_active": "on",
                "permissions": [self.permission.pk],
                "version": version,
                "password": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.email, "updated@example.invalid")

    def test_sign_out_all_invalidates_other_sessions(self):
        other = Client()
        other.force_login(self.staff)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post("/accounts/revoke-sessions/").status_code, 302)
        self.assertEqual(other.get("/staff/customers/").status_code, 302)


@override_settings(STORAGES=STORAGES)
class PasswordResetTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="owner",
            email="owner@example.invalid",
            password=PASSWORD,
            is_staff=True,
            is_superuser=True,
        )
        self.staff = get_user_model().objects.create_user(
            username="staff", email="staff@example.invalid", password=PASSWORD, is_staff=True
        )

    def reset_path(self):
        return re.search(
            r"/accounts/reset/[A-Za-z0-9_-]+/[A-Za-z0-9-]+/", mail.outbox[-1].body
        ).group(0)

    def test_reset_link_single_use_and_password_change_revokes_existing_session(self):
        existing = Client()
        existing.force_login(self.staff)
        self.assertEqual(
            self.client.post("/accounts/password-reset/", {"email": self.staff.email}).status_code,
            302,
        )
        path = self.reset_path()
        response = self.client.get(path)
        self.assertEqual(response.status_code, 302)
        new = "Updated-artificial-password-713!"
        response = self.client.post(response.url, {"new_password1": new, "new_password2": new})
        self.assertEqual(response.status_code, 302)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password(new))
        self.assertEqual(existing.get("/staff/customers/").status_code, 302)
        self.assertFalse(self.client.get(path).context["validlink"])

    def test_unknown_email_is_generic_and_nonstaff_receives_no_link(self):
        get_user_model().objects.create_user(
            username="nonstaff", email="nonstaff@example.invalid", password=PASSWORD
        )
        for email in ["unknown@example.invalid", "nonstaff@example.invalid"]:
            self.assertEqual(
                self.client.post("/accounts/password-reset/", {"email": email}).url,
                "/accounts/password-reset/done/",
            )
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_to_secondary_email_does_not_change_primary_or_bypass_owner_mfa(self):
        profile = AccountSecurity.objects.get(user=self.owner)
        profile.secondary_email = "secondary@example.invalid"
        profile.save()
        self.client.post("/accounts/password-reset/", {"email": profile.secondary_email})
        self.assertEqual(mail.outbox[-1].to, [profile.secondary_email])
        path = self.reset_path()
        response = self.client.get(path)
        new = "Different-artificial-password-712!"
        self.assertEqual(
            self.client.post(
                response.url, {"new_password1": new, "new_password2": new}
            ).status_code,
            302,
        )
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.email, "owner@example.invalid")
        response = self.client.post("/accounts/login/", {"username": "owner", "password": new})
        self.assertEqual(response.url, "/accounts/owner/verify/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_expired_reset_link_rejected(self):
        self.client.post("/accounts/password-reset/", {"email": self.staff.email})
        path = self.reset_path()
        from datetime import datetime

        with patch(
            "django.contrib.auth.tokens.PasswordResetTokenGenerator._now",
            return_value=datetime.now() + timedelta(hours=2),
        ):
            self.assertFalse(self.client.get(path).context["validlink"])

    def test_reset_requests_rate_limited(self):
        for _ in range(5):
            self.client.post("/accounts/password-reset/", {"email": self.staff.email})
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(
            self.client.post("/accounts/password-reset/", {"email": self.staff.email}).status_code,
            429,
        )

    def test_reset_does_not_accept_short_password(self):
        self.client.post("/accounts/password-reset/", {"email": self.staff.email})
        response = self.client.get(self.reset_path())
        self.assertEqual(
            self.client.post(
                response.url, {"new_password1": "short", "new_password2": "short"}
            ).status_code,
            200,
        )
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password(PASSWORD))

    def test_owner_delivery_failure_is_visible_without_authentication_or_secret_logging(self):
        from core.models import SecurityAlert

        with patch(
            "core.account_security.send_mail",
            side_effect=RuntimeError("provider-detail-that-must-not-be-stored"),
        ):
            response = self.client.post(
                "/accounts/login/", {"username": "owner", "password": PASSWORD}
            )
        self.assertEqual(response.url, "/accounts/owner/verify/")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(OwnerChallenge.objects.get().delivered)
        self.assertContains(
            self.client.get("/accounts/owner/verify/"), "We could not send the email."
        )
        self.assertEqual(SecurityAlert.objects.count(), 1)
        self.assertFalse("provider-detail" in str(SecurityAlert.objects.get().details))

    def test_staff_and_owner_mutations_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        verified_owner_login(client, self.owner)
        for path in [
            "/staff/accounts/",
            "/staff/owner-security/codes/",
            "/accounts/revoke-sessions/",
        ]:
            self.assertEqual(client.post(path, {}).status_code, 403)

    def test_recovery_email_change_invalidates_old_reset_links(self):
        self.client.post("/accounts/password-reset/", {"email": self.owner.email})
        path = self.reset_path()
        profile = AccountSecurity.objects.get(user=self.owner)
        profile.version += 1
        profile.save()
        self.assertFalse(self.client.get(path).context["validlink"])

    def test_email_delivery_flag_is_truthful(self):
        self.client.post("/accounts/login/", {"username": "owner", "password": PASSWORD})
        response = self.client.get("/accounts/owner/verify/")
        self.assertTrue(response.context["delivered"])
        self.assertNotContains(response, "We could not send the email.")

    def test_reverse_permission_removal_invalidates_sessions(self):
        permission = Permission.objects.get(
            content_type__app_label="core", codename="view_customer"
        )
        self.staff.user_permissions.add(permission)
        self.client.force_login(self.staff)
        permission.user_set.remove(self.staff)
        self.assertEqual(self.client.get("/staff/customers/").status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_reverse_group_permission_clear_invalidates_sessions(self):
        permission = Permission.objects.get(
            content_type__app_label="core", codename="view_customer"
        )
        group = Group.objects.create(name="Grouped staff")
        group.permissions.add(permission)
        self.staff.groups.add(group)
        self.client.force_login(self.staff)
        permission.group_set.clear()
        self.assertEqual(self.client.get("/staff/customers/").status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_nonsecurity_partial_save_does_not_revoke_healthy_session(self):
        version = AccountSecurity.objects.get(user=self.staff).version
        self.staff.email = "not-saved@example.invalid"
        self.staff.last_login = timezone.now()
        self.staff.save(update_fields=["last_login"])
        self.assertEqual(AccountSecurity.objects.get(user=self.staff).version, version)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.email, "staff@example.invalid")

    def test_reset_delivery_failure_is_generic_and_does_not_log_provider_details(self):
        from core.models import SecurityAlert

        with patch(
            "django.core.mail.message.EmailMultiAlternatives.send",
            side_effect=RuntimeError("private-provider-response"),
        ):
            response = self.client.post("/accounts/password-reset/", {"email": self.staff.email})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SecurityAlert.objects.count(), 1)
        self.assertFalse("private-provider-response" in str(SecurityAlert.objects.get().details))
