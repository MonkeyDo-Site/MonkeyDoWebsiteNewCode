from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from core.models import Customer, Session, SiteSettings


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class PageTests(TestCase):
    def test_all_public_pages_render_without_exact_address(self):
        for path in ("/", "/about/", "/memberships-clubs-parties/", "/contact/", "/book/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "TEST MODE")
                self.assertNotContains(response, "56 Budleman")
                self.assertContains(response, "Skip to content")

    def test_preview_and_staff_content_are_not_cacheable_or_indexable(self):
        response = self.client.get("/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_password_login_lands_on_today(self):
        user = get_user_model().objects.create_user(
            username="login-staff", password="artificial-test-password-123", is_staff=True
        )
        user.user_permissions.add(Permission.objects.get(codename="view_booking"))
        response = self.client.post(
            "/accounts/login/",
            {"username": "login-staff", "password": "artificial-test-password-123"},
        )
        self.assertRedirects(response, "/staff/today/")

    def test_club_visibility_does_not_delete_data(self):
        SiteSettings.objects.create(clubs_visible=False)
        response = self.client.get("/memberships-clubs-parties/")
        self.assertNotContains(response, "<h3>Sunday Club</h3>")
        self.assertEqual(SiteSettings.objects.count(), 1)

    def test_no_public_booking_write_endpoint(self):
        self.assertEqual(self.client.post("/book/", {}).status_code, 405)

    def test_staff_page_denies_anonymous_and_unpermitted_accounts(self):
        self.assertEqual(self.client.get("/staff/today/").status_code, 302)
        user = get_user_model().objects.create_user(username="no-permission")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/staff/today/").status_code, 403)

    def test_staff_page_authorized_and_read_only(self):
        user = get_user_model().objects.create_user(username="staff", is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename="view_booking"))
        self.client.force_login(user)
        response = self.client.get("/staff/today/")
        self.assertContains(response, "No test bookings for today.")
        self.assertContains(response, "Read-only foundation preview.")

    @override_settings(APP_ENV="staging", SECURE_SSL_REDIRECT=False)
    def test_staging_gate_protects_pages_and_health(self):
        from django.contrib.auth.hashers import make_password
        from django.utils import timezone

        SiteSettings.objects.create(
            staging_password_hash=make_password("Artificial-staging-password-172!"),
            staging_password_changed_at=timezone.now(),
        )
        for path in ("/", "/book/", "/health/", "/admin/"):
            self.assertEqual(self.client.get(path).status_code, 302)
        self.assertEqual(self.client.get("/accounts/login/").status_code, 200)
        self.client.post(
            "/staging/access/", {"password": "Artificial-staging-password-172!"}, secure=True
        )
        self.assertEqual(self.client.get("/", secure=True).status_code, 200)
        self.assertEqual(self.client.get("/staff/today/", secure=True).status_code, 302)

    def test_seed_is_idempotent_and_never_changes_existing_sessions(self):
        call_command("seed_staging", stdout=StringIO())
        count = Session.objects.count()
        session = Session.objects.first()
        session.closed = True
        session.save()
        call_command("seed_staging", stdout=StringIO())
        session.refresh_from_db()
        self.assertTrue(session.closed)
        self.assertEqual(count, Session.objects.count())
        self.assertFalse(any(s.starts_at.weekday() == 5 for s in Session.objects.all()))

    def test_session_end_and_capacity_database_constraints(self):
        call_command("seed_staging", stdout=StringIO())
        session = Session.objects.first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Session.objects.filter(pk=session.pk).update(ends_at=session.starts_at)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Session.objects.filter(pk=session.pk).update(supervised_capacity=36)

    def test_customer_phone_unique_and_id_starts_at_one(self):
        c = Customer.objects.create(
            last_name="Test", phone="2025550101", email="test@example.invalid"
        )
        self.assertEqual(c.customer_number, f"{c.pk:06d}")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Customer.objects.create(last_name="Duplicate", phone=c.phone, email=c.email)
