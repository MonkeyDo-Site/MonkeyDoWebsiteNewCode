import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class ConfigurationTests(SimpleTestCase):
    def load_settings(self, **values):
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("APP_ENV", "DJANGO_", "POSTGRES_"))
        }
        env.update(values)
        return subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            env=env,
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_production_cannot_be_enabled_accidentally(self):
        result = self.load_settings(APP_ENV="production")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Production activation is not implemented", result.stderr)

    def test_staging_requires_private_key_hosts_and_postgres(self):
        common = dict(
            APP_ENV="staging",
            DJANGO_SECRET_KEY="test-configuration-only-" * 3,
            DJANGO_ALLOWED_HOSTS="staging.example.invalid",
            POSTGRES_DB="artificial_test",
        )
        for missing in ("DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "POSTGRES_DB"):
            values = {key: value for key, value in common.items() if key != missing}
            with self.subTest(missing=missing):
                self.assertNotEqual(self.load_settings(**values).returncode, 0)
        self.assertEqual(self.load_settings(**common).returncode, 0)

    def test_forwarded_https_is_not_trusted_by_default(self):
        for enabled, expected in (("0", "False"), ("1", "True")):
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import config.settings as s; print(hasattr(s, 'SECURE_PROXY_SSL_HEADER'))",
                ],
                cwd=settings.BASE_DIR,
                env={**os.environ, "APP_ENV": "test", "DJANGO_TRUST_PROXY": enabled},
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), expected)
