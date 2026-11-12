from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings

from core.models import AuditEvent, Customer, SiteSettings
from core.website_settings import save_club_visibility
from tests.helpers import verified_owner_login
from tests.test_customers import staff_user
from tests.test_owner_accounts import STORAGES


@override_settings(STORAGES=STORAGES)
class WebsiteSettingsTests(TestCase):
    def setUp(self):
        self.owner = staff_user("owner", owner=True)
        self.staff = staff_user()
        self.site = SiteSettings.objects.create(
            clubs_visible=False, booking_horizon_days=7, staging_password_hash="unchanged-test-hash"
        )

    def test_owner_can_enable_and_disable_saved_content_without_deleting_records(self):
        Customer.objects.create(
            last_name="Fictional", phone="2025550101", email="a@example.invalid"
        )
        verified_owner_login(self.client, self.owner)
        self.assertContains(
            self.client.get("/staff/website-settings/"), "Show clubs on the website"
        )
        for visible, expected in ((True, 0), (False, 1)):
            data = {"expected_clubs_visible": expected}
            if visible:
                data["clubs_visible"] = "on"
            self.assertRedirects(
                self.client.post("/staff/website-settings/", data), "/staff/website-settings/"
            )
            self.site.refresh_from_db()
            self.assertEqual(self.site.clubs_visible, visible)
            home = self.client.get("/")
            parties = self.client.get("/clubs-parties/")
            booking = self.client.get("/book/")
            for response in (home, parties, booking):
                if visible:
                    self.assertContains(response, "Clubs &amp; Parties")
                else:
                    self.assertNotContains(response, "Clubs &amp; Parties")
            for response in (home, parties):
                self.assertContains(response, "MonkeyDo Parties")
                if visible:
                    self.assertContains(response, "Sunday Club")
                else:
                    self.assertNotContains(response, "Sunday Club")
            self.assertEqual(Customer.objects.count(), 1)
            self.assertEqual(self.site.booking_horizon_days, 7)
            self.assertEqual(self.site.staging_password_hash, "unchanged-test-hash")
        events = AuditEvent.objects.filter(action="website.clubs_visibility_changed")
        self.assertEqual(events.count(), 2)
        self.assertTrue(all(event.actor == self.owner for event in events))

    def test_staff_with_model_permission_still_cannot_change_owner_setting(self):
        self.staff.user_permissions.add(Permission.objects.get(codename="change_sitesettings"))
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/staff/website-settings/").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/staff/website-settings/", {"clubs_visible": "on", "expected_clubs_visible": 0}
            ).status_code,
            403,
        )
        with self.assertRaises(PermissionDenied):
            save_club_visibility(actor=self.staff, clubs_visible=True, expected_clubs_visible=False)
        self.site.refresh_from_db()
        self.assertFalse(self.site.clubs_visible)

    def test_anonymous_access_requires_login_and_owner_posts_require_csrf(self):
        self.assertEqual(self.client.get("/staff/website-settings/").status_code, 302)
        secured = Client(enforce_csrf_checks=True)
        verified_owner_login(secured, self.owner)
        self.assertEqual(
            secured.post(
                "/staff/website-settings/", {"clubs_visible": "on", "expected_clubs_visible": 0}
            ).status_code,
            403,
        )

    def test_stale_form_rejected_without_overwriting_current_value(self):
        save_club_visibility(actor=self.owner, clubs_visible=True, expected_clubs_visible=False)
        with self.assertRaises(ValidationError):
            save_club_visibility(
                actor=self.owner, clubs_visible=False, expected_clubs_visible=False
            )
        self.site.refresh_from_db()
        self.assertTrue(self.site.clubs_visible)
        self.assertEqual(
            AuditEvent.objects.filter(action="website.clubs_visibility_changed").count(), 1
        )

    def test_audit_failure_rolls_back_visibility(self):
        with patch("core.website_settings.AuditEvent.objects.create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                save_club_visibility(
                    actor=self.owner, clubs_visible=True, expected_clubs_visible=False
                )
        self.site.refresh_from_db()
        self.assertFalse(self.site.clubs_visible)

    def test_no_settings_defaults_to_hidden_without_read_side_effect(self):
        self.site.delete()
        response = self.client.get("/")
        self.assertNotContains(response, "Sunday Club")
        self.assertContains(response, "MonkeyDo Parties")
        self.assertEqual(SiteSettings.objects.count(), 0)
