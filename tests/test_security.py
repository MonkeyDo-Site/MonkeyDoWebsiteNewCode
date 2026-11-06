from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import LoginThrottle, SecurityAlert
from tests.helpers import verified_owner_login
from tests.test_customers import staff_user


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class LoginProtectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="test-staff", password="artificial-password-123", is_staff=True
        )
        self.now = timezone.now()

    def attempt(self, password="incorrect-test-password", username="test-staff"):
        with patch("core.security.timezone.now", return_value=self.now):
            return self.client.post(
                "/accounts/login/", {"username": username, "password": password}
            )

    def test_five_failures_start_temporary_progressive_delay(self):
        for _ in range(5):
            self.assertEqual(self.attempt().status_code, 200)
        blocked = self.attempt(password="artificial-password-123")
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked["Retry-After"], "1")
        self.now += timedelta(seconds=1)
        self.assertEqual(self.attempt().status_code, 200)
        self.assertEqual(self.attempt()["Retry-After"], "2")
        self.now += timedelta(seconds=2)
        self.assertEqual(self.attempt(password="artificial-password-123").status_code, 302)
        self.assertEqual(LoginThrottle.objects.get(key__startswith="account:").failures, 0)

    def test_window_expires_without_permanent_lockout(self):
        for _ in range(5):
            self.attempt()
        self.now += timedelta(minutes=16)
        self.assertEqual(self.attempt(password="artificial-password-123").status_code, 302)

    def test_repeated_failures_create_one_persistent_alert(self):
        for _ in range(10):
            self.attempt()
            self.now += timedelta(minutes=1)
        self.assertEqual(SecurityAlert.objects.count(), 1)
        self.assertEqual(SecurityAlert.objects.get().details["attempts"], 10)
        self.assertNotIn("password", str(SecurityAlert.objects.get().details))

    def test_unknown_user_has_same_delay_and_no_raw_username_in_buckets(self):
        for _ in range(5):
            self.attempt(username="unknown-account")
        self.assertEqual(self.attempt(username="unknown-account").status_code, 429)
        self.assertFalse(LoginThrottle.objects.filter(key__contains="unknown-account").exists())

    def test_network_limit_applies_across_usernames(self):
        for i in range(25):
            self.attempt(username=f"unknown-{i}")
        self.assertEqual(self.attempt(username="different-account").status_code, 429)
        self.assertEqual(LoginThrottle.objects.filter(key__startswith="account:").count(), 25)

    def test_non_staff_cannot_sign_in_even_with_correct_password(self):
        get_user_model().objects.create_user(
            username="non-staff", password="artificial-password-123"
        )
        self.assertEqual(
            self.attempt(username="non-staff", password="artificial-password-123").status_code, 200
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_alert_dashboard_and_resolution_are_owner_only(self):
        owner = staff_user("owner", owner=True)
        staff = staff_user("normal-staff")
        alert = SecurityAlert.objects.create(
            subject="Sensitive security notice", details={"scope": "account", "attempts": 10}
        )
        self.client.force_login(staff)
        self.assertNotContains(self.client.get("/staff/dashboard/"), "Sensitive security notice")
        self.assertEqual(
            self.client.post(f"/staff/security-alerts/{alert.pk}/resolve/").status_code, 403
        )
        verified_owner_login(self.client, owner)
        self.assertContains(self.client.get("/staff/dashboard/"), "Sensitive security notice")
        self.assertEqual(
            self.client.get(f"/staff/security-alerts/{alert.pk}/resolve/").status_code, 405
        )
        self.assertEqual(
            self.client.post(f"/staff/security-alerts/{alert.pk}/resolve/").status_code, 302
        )
        alert.refresh_from_db()
        self.assertEqual(alert.resolved_by, owner)

    def test_inspector_does_not_offer_unthrottled_password_endpoint(self):
        response = self.client.post(
            "/admin/login/?next=/admin/",
            {"username": "test-staff", "password": "artificial-password-123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/accounts/login/?next=/admin/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unicode_username_normalization_cannot_bypass_account_delay(self):
        for name in [
            "test-staff",
            "ｔｅｓｔ－ｓｔａｆｆ",
            "test-staff",
            "ｔｅｓｔ－ｓｔａｆｆ",
            "test-staff",
        ]:
            self.assertEqual(self.attempt(username=name).status_code, 200)
        self.assertEqual(self.attempt(password="artificial-password-123").status_code, 429)
        self.assertEqual(LoginThrottle.objects.filter(key__startswith="account:").count(), 1)

    def test_blocked_request_does_not_check_credentials(self):
        for _ in range(5):
            self.attempt()
        with patch(
            "django.contrib.auth.forms.authenticate",
            side_effect=AssertionError("Blocked request checked password"),
        ):
            self.assertEqual(self.attempt(password="artificial-password-123").status_code, 429)
