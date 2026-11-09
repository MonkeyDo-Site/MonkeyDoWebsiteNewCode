from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings

from core.models import Booking, Customer, SiteSettings
from core.staging_access import set_staging_password
from tests import test_customers as customers
from tests.test_owner_accounts import STORAGES


@override_settings(
    ROOT_URLCONF="config.design_preview_urls",
    APP_ENV="staging",
    DESIGN_REVIEW_ONLY=True,
    SECURE_SSL_REDIRECT=False,
    STORAGES=STORAGES,
)
class HostedDesignReviewTests(TestCase):
    def setUp(self):
        self.owner = customers.staff_user("owner", owner=True)
        self.password = "Artificial-preview-password-9aX!"
        set_staging_password(owner=self.owner, password=self.password)

    def unlock(self, client=None):
        return (client or self.client).post(
            "/staging/access/", {"password": self.password}, secure=True
        )

    def test_gate_is_required_and_uses_existing_secure_ticket(self):
        self.assertRedirects(
            self.client.get("/", secure=True), "/staging/access/", fetch_redirect_response=False
        )
        response = self.client.get("/staging/access/", secure=True)
        self.assertContains(response, "Private design review")
        self.assertNotContains(response, "Staff areas require")
        response = self.unlock()
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertTrue(response.cookies["monkeydo_staging_access"]["secure"])
        self.assertTrue(response.cookies["monkeydo_staging_access"]["httponly"])
        self.assertContains(self.client.get("/", secure=True), "Design review V4")

    def test_pages_are_frozen_read_only_and_assets_are_root_relative(self):
        self.unlock()
        for path in [
            "/01-home.html",
            "/08-customer.html",
            "/13-membership.html",
            "/16-weekly.html",
        ]:
            response = self.client.get(path, secure=True)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "<form")
            self.assertNotContains(response, "csrfmiddlewaretoken")
            self.assertNotContains(response, "<script")
            self.assertContains(response, "/static/core/site.css")
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertIn("form-action 'none'", response["Content-Security-Policy"])
            self.assertEqual(self.client.post(path, {}, secure=True).status_code, 405)
        self.assertFalse(Customer.objects.exists())
        self.assertFalse(Booking.objects.exists())

    def test_no_operational_routes_or_arbitrary_files_are_exposed(self):
        self.unlock()
        for path in [
            "/staff/customers/",
            "/staff/bookings/new/",
            "/staff/accounts/",
            "/admin/",
            "/accounts/login/",
            "/config/settings.py",
            "/.env",
            "/manifest.json",
            "/unknown.html",
        ]:
            self.assertEqual(self.client.get(path, secure=True).status_code, 404, path)

    def test_screenshots_are_gated_and_not_cacheable(self):
        self.assertEqual(self.client.get("/01-home-phone.jpg", secure=True).status_code, 302)
        self.unlock()
        response = self.client.get("/01-home-phone.jpg", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        response.close()

    def test_rotation_invalidates_prior_access_and_csrf_is_enforced(self):
        self.unlock()
        set_staging_password(owner=self.owner, password=self.password)
        self.assertEqual(self.client.get("/", secure=True).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.unlock(client).status_code, 403)

    def test_command_hides_password_and_uses_owner_audit(self):
        output = StringIO()
        with patch(
            "core.management.commands.set_design_review_password.getpass",
            side_effect=[self.password, self.password],
        ):
            call_command("set_design_review_password", owner="owner", stdout=output)
        self.assertNotIn(self.password, output.getvalue())
        self.assertIn("saved", output.getvalue())
        with override_settings(DESIGN_REVIEW_ONLY=False), self.assertRaises(CommandError):
            call_command("set_design_review_password", owner="owner", stdout=StringIO())

    def test_command_mismatch_leaves_existing_hash_unchanged(self):
        before = SiteSettings.objects.get().staging_password_hash
        with (
            patch(
                "core.management.commands.set_design_review_password.getpass",
                side_effect=[self.password, "different"],
            ),
            self.assertRaises(CommandError),
        ):
            call_command("set_design_review_password", owner="owner", stdout=StringIO())
        self.assertEqual(SiteSettings.objects.get().staging_password_hash, before)
