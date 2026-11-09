import base64
import os
import tempfile
from pathlib import Path
from unittest import TestCase

from deploy import monkeydo_deploy as deploy


class FunctionalDeploymentTests(TestCase):
    def setUp(self):
        deploy.select_target("functional")

    def tearDown(self):
        deploy.select_target("design")

    def environment(self):
        return {
            "APP_ENV": "staging",
            "MONKEYDO_DESIGN_ONLY": "0",
            "MONKEYDO_CUSTOMER_TEST_BOOKING": "1",
            "DJANGO_SECRET_KEY": "x" * 60,
            "DJANGO_ALLOWED_HOSTS": "staging.monkeydoplay.com",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://staging.monkeydoplay.com",
            "DJANGO_TRUST_PROXY": "1",
            "MONKEYDO_TRUST_LOCAL_CLIENT_IP": "1",
            "POSTGRES_DB": "monkeydo_functional",
            "POSTGRES_USER": "monkeydo-functional",
            "POSTGRES_HOST": "/var/run/postgresql",
            "MONKEYDO_EMAIL_TRANSPORT": "resend",
            "RESEND_API_KEY": "fake-local-test-key",
            "MONKEYDO_TEST_EMAIL_RECIPIENTS": "owner@example.invalid",
        }

    def read(self, env):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.env"
            path.write_text("".join(f"{k}={v}\n" for k, v in env.items()))
            path.chmod(0o600)
            return deploy.read_environment(path, owner_uid=os.getuid())

    def test_target_paths_roles_health_and_private_configuration_are_isolated(self):
        self.assertEqual(deploy.BASE, Path("/srv/monkeydo-functional"))
        self.assertEqual(deploy.STATE, Path("/var/lib/monkeydo-functional-deploy"))
        self.assertEqual(deploy.UNIT, "monkeydo-functional.service")
        self.assertEqual(self.read(self.environment())["POSTGRES_DB"], "monkeydo_functional")
        self.assertIn(("/staff/", 200), deploy.HEALTH_PATHS)
        self.assertIn(("/book/details/", 302), deploy.HEALTH_PATHS)
        self.assertNotIn(("/01-home.html", 302), deploy.HEALTH_PATHS)
        for field, value in (
            ("POSTGRES_DB", "monkeydo_staging"),
            ("POSTGRES_USER", "monkeydo"),
            ("DJANGO_ALLOWED_HOSTS", "testing.monkeydoplay.com"),
            ("MONKEYDO_DESIGN_ONLY", "1"),
            ("MONKEYDO_CUSTOMER_TEST_BOOKING", "0"),
        ):
            with self.subTest(field=field), self.assertRaises(deploy.DeployError):
                self.read(self.environment() | {field: value})
        for field in ("RESEND_API_KEY", "MONKEYDO_TEST_EMAIL_RECIPIENTS"):
            env = self.environment()
            env.pop(field)
            with self.assertRaises(deploy.DeployError):
                self.read(env)

    def test_service_override_selects_functional_environment_and_cannot_replace_design(self):
        host = deploy.Host(self.environment(), Path("/tmp/unused-functional-log"))
        self.assertEqual(host.current, Path("/srv/monkeydo-functional/staging/current"))
        snapshot = host.candidate_snapshot(Path("/srv/monkeydo-functional/releases/review"))
        content = base64.b64decode(snapshot["dropin"]).decode()
        for text in (
            "EnvironmentFile=/etc/monkeydo/functional.env",
            "MONKEYDO_DESIGN_ONLY=0",
            "MONKEYDO_CUSTOMER_TEST_BOOKING=1",
            "--workers 1",
            "/run/monkeydo-functional/gunicorn.sock",
        ):
            self.assertIn(text, content)
        self.assertNotIn("/srv/monkeydo/staging", content)

    def test_design_defaults_are_preserved_when_selected(self):
        deploy.select_target("design")
        self.assertEqual(deploy.BASE, Path("/srv/monkeydo"))
        self.assertEqual(deploy.UNIT, "monkeydo-design-review.service")
        self.assertEqual(deploy.RUNTIME_USER, "monkeydo")
        content = base64.b64decode(
            deploy.Host({}, Path("/tmp/unused")).candidate_snapshot(
                Path("/srv/monkeydo/releases/review")
            )["dropin"]
        ).decode()
        self.assertIn("MONKEYDO_DESIGN_ONLY=1", content)
        self.assertNotIn("MONKEYDO_CUSTOMER_TEST_BOOKING=1", content)

    def test_unknown_target_rejected(self):
        with self.assertRaises(ValueError):
            deploy.select_target("production")
