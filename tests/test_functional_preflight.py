from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from core.middleware import LocalProxyClientIPMiddleware
from core.models import SiteSettings
from tests.test_customers import staff_user


@override_settings(
    APP_ENV="staging",
    DEBUG=False,
    DESIGN_REVIEW_ONLY=False,
    CUSTOMER_TEST_BOOKING=True,
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
    SECURE_SSL_REDIRECT=True,
    ALLOWED_HOSTS=["testing.monkeydoplay.com"],
    CSRF_TRUSTED_ORIGINS=["https://testing.monkeydoplay.com"],
    TRUST_LOCAL_CLIENT_IP=True,
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    EMAIL_BACKEND="core.test_email.StagingEmailBackend",
    RESEND_API_KEY="fake-local-key",
    STAGING_EMAIL_RECIPIENTS=("owner@example.invalid",),
)
class FunctionalPreflightTests(TestCase):
    def setUp(self):
        self.owner = staff_user("owner", owner=True)
        self.owner.email = "owner@example.invalid"
        self.owner.save()
        SiteSettings.objects.create(
            staging_password_hash=make_password("Test-preview-password-9!"),
            staging_password_changed_at=timezone.now(),
        )

    def run_preflight(self, row=None):
        cursor = MagicMock()
        cursor.fetchone.return_value = row or (
            "monkeydo_functional",
            "monkeydo-functional",
            False,
            True,
            False,
            False,
            False,
        )
        manager = MagicMock()
        manager.__enter__.return_value = cursor
        with patch(
            "core.management.commands.functional_staging_preflight.connection",
            SimpleNamespace(vendor="postgresql", cursor=lambda: manager),
        ):
            stream = StringIO()
            call_command("functional_staging_preflight", stdout=stream)
        return stream.getvalue()

    def test_ready_configuration_passes_without_email_or_mutations(self):
        self.assertIn("preflight passed", self.run_preflight())

    def test_design_database_or_schema_privilege_or_missing_allowlist_fail_closed(self):
        for row in (
            ("monkeydo_staging", "monkeydo-functional", False, True, False, False, False),
            ("monkeydo_functional", "monkeydo-functional", True, True, False, False, False),
        ):
            with self.assertRaises(CommandError):
                self.run_preflight(row)
        with override_settings(STAGING_EMAIL_RECIPIENTS=()), self.assertRaises(CommandError):
            self.run_preflight()
        with override_settings(DESIGN_REVIEW_ONLY=True), self.assertRaises(CommandError):
            self.run_preflight()

    def test_expired_private_gate_blocks_readiness(self):
        SiteSettings.objects.update(
            staging_password_changed_at=timezone.now() - timezone.timedelta(days=91)
        )
        with self.assertRaises(CommandError):
            self.run_preflight()


class ProxyIPTests(TestCase):
    def resolve(self, peer, real=None, forwarded=None):
        request = RequestFactory().get(
            "/", REMOTE_ADDR=peer, HTTP_X_REAL_IP=real or "", HTTP_X_FORWARDED_FOR=forwarded or ""
        )
        LocalProxyClientIPMiddleware(lambda r: HttpResponse())(request)
        return request.META["REMOTE_ADDR"]

    @override_settings(TRUST_LOCAL_CLIENT_IP=True)
    def test_only_reviewed_local_connection_can_supply_client_ip(self):
        self.assertEqual(self.resolve("127.0.0.1", "203.0.113.10"), "203.0.113.10")
        self.assertEqual(self.resolve("198.51.100.9", "203.0.113.10"), "198.51.100.9")
        self.assertEqual(self.resolve("127.0.0.1", "invalid"), "127.0.0.1")
        self.assertEqual(self.resolve("127.0.0.1", forwarded="203.0.113.10"), "127.0.0.1")

    @override_settings(TRUST_LOCAL_CLIENT_IP=False)
    def test_default_ignores_forwarded_identity(self):
        self.assertEqual(self.resolve("127.0.0.1", "203.0.113.10"), "127.0.0.1")
