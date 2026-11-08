"""Exercise Django's real migration check on the disposable PostgreSQL test DB."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import skipUnless

from django.db import connection
from django.test import TransactionTestCase


@skipUnless(
    connection.vendor == "postgresql", "Migration guard integration uses disposable PostgreSQL."
)
class DeploymentMigrationGuardTests(TransactionTestCase):
    def test_pending_schema_change_is_reported_without_running_it(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            module = temporary / "deploy_probe"
            module.mkdir()
            (module / "__init__.py").write_text("")
            shutil.copytree(root / "core/migrations", module / "migrations")
            migrations = sorted((module / "migrations").glob("[0-9]*.py"))
            last = migrations[-1].stem
            (module / "migrations/9999_deployment_probe.py").write_text(
                "from django.db import migrations\nclass Migration(migrations.Migration):\n    dependencies=[('core',"
                + repr(last)
                + ")]\n    operations=[migrations.RunSQL('CREATE TABLE core_deployment_probe (id integer)')]\n"
            )
            database = {
                key: connection.settings_dict[key]
                for key in ("ENGINE", "NAME", "USER", "PASSWORD", "HOST", "PORT")
            }
            # This fixture contains only disposable test credentials, is outside
            # Git, and is deleted with its private temporary directory.
            (module / "settings.py").write_text(
                "from config.settings import *\nDATABASES="
                + repr({"default": database})
                + "\nMIGRATION_MODULES={'core':'deploy_probe.migrations'}\n"
            )
            environment = dict(
                os.environ,
                DJANGO_SETTINGS_MODULE="deploy_probe.settings",
                APP_ENV="test",
                PYTHONPATH=str(temporary) + os.pathsep + str(root),
            )
            result = subprocess.run(
                [sys.executable, str(root / "manage.py"), "migrate", "--check"],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('core_deployment_probe')")
                self.assertIsNone(cursor.fetchone()[0])
