"""Real CMS authentication round trip plus retention/privacy/owner access boundaries."""

import hashlib
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import skipUnless

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.backups.models import BackupRun
from core.backups.services import encrypt_dump, retained_ids
from core.backups.storage import BackupUnavailable
from tests import test_scheduling as fixtures
from tests.helpers import verified_owner_login
from tests.test_owner_accounts import STORAGES


class EncryptionTests(SimpleTestCase):
    @skipUnless(
        shutil.which("openssl") and os.name == "posix", "Local OpenSSL and POSIX fixture required"
    )
    def test_real_authenticated_encryption_roundtrip_and_wrong_key_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            key, cert, wrong = folder / "key.pem", folder / "public.pem", folder / "wrong.pem"
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-keyout",
                    str(key),
                    "-out",
                    str(cert),
                    "-days",
                    "1",
                    "-nodes",
                    "-subj",
                    "/CN=Fictional local test only",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                [
                    "openssl",
                    "genpkey",
                    "-algorithm",
                    "RSA",
                    "-pkeyopt",
                    "rsa_keygen_bits:2048",
                    "-out",
                    str(wrong),
                ],
                check=True,
                stderr=subprocess.DEVNULL,
            )
            source = folder / "fake-pg-dump"
            source.write_text("#!/bin/sh\nprintf 'PGDMP-fictional-encryption-check-only'\n")
            source.chmod(0o700)
            encrypted = folder / "dump.cms"
            with encrypted.open("w+b") as output:
                _, digest, size = encrypt_dump(
                    output,
                    database={},
                    certificate=cert,
                    pg_dump=str(source),
                    openssl=shutil.which("openssl"),
                )
            self.assertEqual(digest, hashlib.sha256(encrypted.read_bytes()).hexdigest())
            self.assertEqual(size, encrypted.stat().st_size)
            self.assertNotIn(b"PGDMP-fictional", encrypted.read_bytes())
            result = subprocess.run(
                [
                    "openssl",
                    "cms",
                    "-decrypt",
                    "-binary",
                    "-inform",
                    "DER",
                    "-in",
                    str(encrypted),
                    "-inkey",
                    str(key),
                ],
                capture_output=True,
                check=True,
            )
            self.assertEqual(result.stdout, b"PGDMP-fictional-encryption-check-only")
            result = subprocess.run(
                [
                    "openssl",
                    "cms",
                    "-decrypt",
                    "-binary",
                    "-inform",
                    "DER",
                    "-in",
                    str(encrypted),
                    "-inkey",
                    str(wrong),
                ],
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            broken = bytearray(encrypted.read_bytes())
            broken[-1] ^= 1
            encrypted.write_bytes(broken)
            result = subprocess.run(
                [
                    "openssl",
                    "cms",
                    "-decrypt",
                    "-binary",
                    "-inform",
                    "DER",
                    "-in",
                    str(encrypted),
                    "-inkey",
                    str(key),
                ],
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            with encrypted.open("w+b") as output, self.assertRaises(BackupUnavailable):
                encrypt_dump(output, database={}, certificate=key)

    def test_retention_keeps_seven_nightly_and_twelve_distinct_months(self):
        rows = [
            SimpleNamespace(
                pk=uuid.uuid4(),
                monthly=i in range(7, 25),
                month=f"{2026 - i // 12:04d}-{12 - i % 12:02d}",
            )
            for i in range(26)
        ]
        rows.insert(9, SimpleNamespace(pk=uuid.uuid4(), monthly=True, month=rows[8].month))
        keep = retained_ids(rows)
        self.assertTrue(all(row.pk in keep for row in rows[:7]))
        self.assertEqual(len(keep), 19)
        self.assertNotIn(rows[-1].pk, keep)


@override_settings(BACKUP_ENABLED=True, STORAGES=STORAGES)
class OwnerBackupTests(TestCase):
    setUp = fixtures.SchedulingTests.setUp

    def test_staff_cannot_access_archive_or_restore_controls(self):
        backup = BackupRun.objects.create(
            object_key="staging/backups/2026-11-" + uuid.uuid4().hex + ".cms",
            month="2026-11",
            state="verified",
            verified_at=timezone.now(),
            sha256="a" * 64,
        )
        self.client.force_login(self.staff)
        for url in [
            reverse("backups"),
            reverse("backup_download", args=[backup.pk]),
            reverse("backup_manifest", args=[backup.pk]),
            reverse("backup_restore", args=[backup.pk]),
        ]:
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_owner_empty_state_does_not_claim_a_backup_exists(self):
        verified_owner_login(self.client, self.owner)
        response = self.client.get(reverse("backups"))
        self.assertContains(response, "No backup run has been recorded")
        self.assertContains(response, "An isolated restore test is due")
