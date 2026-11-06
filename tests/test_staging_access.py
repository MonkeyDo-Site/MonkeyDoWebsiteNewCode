from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.utils import timezone

from core.staging_access import COOKIE, set_staging_password
from tests.helpers import verified_owner_login
from tests.test_owner_accounts import STORAGES


@override_settings(APP_ENV="staging", SECURE_SSL_REDIRECT=False, STORAGES=STORAGES)
class StagingAccessTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="owner", email="owner@example.invalid", is_staff=True, is_superuser=True
        )
        self.password = "Artificial-shared-staging-193!"
        self.site = set_staging_password(owner=self.owner, password=self.password)

    def test_shared_password_allows_public_preview_but_not_staff_portal(self):
        self.assertEqual(self.client.get("/").url, "/staging/access/")
        response = self.client.post("/staging/access/", {"password": self.password}, secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.cookies[COOKIE]["secure"])
        self.assertTrue(response.cookies[COOKIE]["httponly"])
        self.assertEqual(self.client.get("/", secure=True).status_code, 200)
        self.assertEqual(self.client.get("/staff/customers/", secure=True).status_code, 302)

    def test_staging_password_is_hashed_and_owner_rotation_revokes_old_tickets(self):
        self.assertFalse(self.site.staging_password_hash == self.password)
        self.client.post("/staging/access/", {"password": self.password}, secure=True)
        set_staging_password(owner=self.owner, password="Changed-shared-staging-184!")
        self.assertEqual(self.client.get("/", secure=True).url, "/staging/access/")

    def test_password_expires_at_ninety_days_and_owner_can_recover_setup(self):
        with patch(
            "django.utils.timezone.now",
            return_value=self.site.staging_password_changed_at + timedelta(days=90),
        ):
            self.assertEqual(
                self.client.post(
                    "/staging/access/", {"password": self.password}, secure=True
                ).status_code,
                200,
            )
        verified_owner_login(self.client, self.owner)
        self.assertEqual(self.client.get("/staff/staging-access/", secure=True).status_code, 200)
        self.assertEqual(
            self.client.post(
                "/staff/staging-access/", {"password": "Replacement-preview-192!"}, secure=True
            ).status_code,
            302,
        )
        self.assertEqual(self.client.get("/", secure=True).status_code, 200)

    def test_tampered_or_old_access_cookie_is_rejected(self):
        self.client.cookies[COOKIE] = "tampered"
        self.assertEqual(self.client.get("/", secure=True).status_code, 302)
        self.client.post("/staging/access/", {"password": self.password}, secure=True)
        with patch(
            "django.core.signing.time.time",
            return_value=timezone.now().timestamp() + 2 * 24 * 60 * 60,
        ):
            self.assertEqual(self.client.get("/", secure=True).status_code, 302)

    def test_staff_cannot_change_shared_password(self):
        staff = get_user_model().objects.create_user(username="staff", is_staff=True)
        with self.assertRaises(PermissionDenied):
            set_staging_password(owner=staff, password=self.password)
        self.client.force_login(staff)
        self.assertEqual(self.client.get("/staff/staging-access/", secure=True).status_code, 302)
        self.client.post("/staging/access/", {"password": self.password}, secure=True)
        self.assertEqual(self.client.get("/staff/staging-access/", secure=True).status_code, 403)

    def test_owner_mfa_required_even_on_bootstrap_settings_route(self):
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get("/staff/staging-access/", secure=True).url, "/accounts/login/"
        )

    def test_gate_attempts_rate_limited(self):
        for _ in range(5):
            self.client.post("/staging/access/", {"password": "wrong"}, secure=True)
        self.assertEqual(
            self.client.post(
                "/staging/access/", {"password": self.password}, secure=True
            ).status_code,
            429,
        )

    def test_settings_inspector_does_not_expose_password_hash(self):
        verified_owner_login(self.client, self.owner)
        self.client.post("/staging/access/", {"password": self.password}, secure=True)
        response = self.client.get("/admin/core/sitesettings/1/change/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.site.staging_password_hash)
