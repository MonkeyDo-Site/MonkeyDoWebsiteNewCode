"""Stream a consistent PG dump directly into authenticated public-key encryption."""

import hashlib
import os
import stat
import subprocess
import tempfile
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

from core.availability import NEW_YORK

from .models import BackupRun
from .storage import MAX_BACKUP, BackupStore, BackupUnavailable


def enabled():
    if not settings.BACKUP_ENABLED or settings.APP_ENV not in {"staging", "test", "development"}:
        raise ValidationError("Encrypted staging backups are not enabled.")


def encrypt_dump(
    output, *, database, certificate, pg_dump="/usr/bin/pg_dump", openssl="/usr/bin/openssl"
):
    cert = Path(certificate)
    if (
        not cert.is_file()
        or cert.is_symlink()
        or cert.stat().st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    ):
        raise BackupUnavailable("public_certificate_permissions")
    # This is a PUBLIC certificate. The private decryption key is never installed here.
    pem = cert.read_bytes()
    if len(pem) > 32768 or b"PRIVATE KEY" in pem or b"BEGIN CERTIFICATE" not in pem:
        raise BackupUnavailable("public_certificate_only")
    fingerprint = hashlib.sha256(
        subprocess.check_output(
            [openssl, "x509", "-in", str(cert), "-outform", "DER"],
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    ).hexdigest()
    env = dict(os.environ)
    for key, setting in (
        ("PGDATABASE", "NAME"),
        ("PGUSER", "USER"),
        ("PGHOST", "HOST"),
        ("PGPORT", "PORT"),
        ("PGPASSWORD", "PASSWORD"),
    ):
        env[key] = str(database.get(setting, ""))
    env["PGCONNECT_TIMEOUT"] = "10"
    dump = subprocess.Popen(
        [pg_dump, "--format=custom", "--no-owner", "--no-acl", "--no-password"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    cipher = None
    try:
        cipher = subprocess.Popen(
            [
                openssl,
                "cms",
                "-encrypt",
                "-aes-256-gcm",
                "-binary",
                "-outform",
                "DER",
                "-recip",
                str(cert),
            ],
            stdin=dump.stdout,
            stdout=output,
            stderr=subprocess.DEVNULL,
        )
        dump.stdout.close()
        if cipher.wait(timeout=600) or dump.wait(timeout=30):
            raise BackupUnavailable("dump_or_encryption_failed")
    finally:
        if cipher is not None and cipher.poll() is None:
            cipher.kill()
            cipher.wait()
        if dump.poll() is None:
            dump.kill()
            dump.wait()
    output.flush()
    output.seek(0, 2)
    size = output.tell()
    if not 0 < size <= MAX_BACKUP:
        raise BackupUnavailable("backup_size")
    output.seek(0)
    digest = hashlib.file_digest(output, "sha256").hexdigest()
    output.seek(0)
    return fingerprint, digest, size


def notify_failure(run):
    if settings.BOOKING_EMAIL_ENABLED:
        from core.communications.services import enqueue

        try:
            enqueue(
                key="backup-failure:" + str(run.pk),
                kind="backup_alert",
                recipient=settings.BOOKING_REPLY_TO,
                subject="MonkeyDo encrypted backup requires review",
                text="An encrypted staging backup or retention check failed. Review the owner Backups page. Recovery point: "
                + str(run.pk)
                + ". No recovery private key is stored on DigitalOcean or R2.",
            )
        except Exception:
            # The persisted BackupRun remains the Dashboard fallback when mail is unavailable.
            pass


def retained_ids(records):
    records = list(records)
    keep = {row.pk for row in records[:7]}
    months = set()
    for row in records:
        if row.monthly and row.month not in months and len(months) < 12:
            months.add(row.month)
            keep.add(row.pk)
    return keep


def run_backup():
    enabled()
    if connection.vendor != "postgresql":
        raise ValidationError("Consistent database backups require PostgreSQL.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", [73222, 1])
        if not cursor.fetchone()[0]:
            raise ValidationError("A backup or retention run is already active.")
    run = None
    try:
        # Interrupted runs are never passed off as verified or used to expire recovery points.
        BackupRun.objects.filter(state="running").update(state="failed", code="interrupted_backup")
        month = timezone.localdate(timezone=NEW_YORK).strftime("%Y-%m")
        key = uuid.uuid4()
        monthly = not BackupRun.objects.filter(
            month=month, monthly=True, state__in=["verified", "retention_failed"]
        ).exists()
        run = BackupRun.objects.create(
            id=key,
            month=month,
            monthly=monthly,
            object_key=f"staging/backups/{month}-{key.hex}.cms",
        )
        store = BackupStore()
        # Only ciphertext touches temporary disk; plaintext streams from pg_dump into CMS.
        with tempfile.TemporaryFile(mode="w+b") as output:
            cert, digest, size = encrypt_dump(
                output,
                database=settings.DATABASES["default"],
                certificate=settings.BACKUP_ENCRYPTION_CERTIFICATE,
            )
            run.sha256, run.size, run.encryption_fingerprint = digest, size, cert
            run.save(update_fields=["sha256", "size", "encryption_fingerprint"])
            store.put(run.object_key, output, digest, size)
        run.state, run.sha256, run.size, run.encryption_fingerprint = "verified", digest, size, cert
        run.verified_at = timezone.now()
        run.save()
        records = list(
            BackupRun.objects.filter(state__in=["verified", "retention_failed"]).order_by(
                "-verified_at", "-pk"
            )
        )
        keep = retained_ids(records)
        try:
            for old in records:
                if old.pk in keep:
                    continue
                store.delete(old.object_key)
                old.state, old.removed_at = "removed", timezone.now()
                old.save(update_fields=["state", "removed_at"])
        except Exception:
            run.state, run.code = "retention_failed", "retention_review"
            run.save(update_fields=["state", "code"])
            notify_failure(run)
        return run
    except Exception:
        if run is not None and run.state == "running":
            run.state, run.code = "failed", "backup_review"
            run.save(update_fields=["state", "code"])
            notify_failure(run)
        raise BackupUnavailable("backup_review") from None
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s, %s)", [73222, 1])
