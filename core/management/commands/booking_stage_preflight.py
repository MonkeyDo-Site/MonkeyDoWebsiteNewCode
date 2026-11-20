"""Read-only configuration/privilege checks; no provider call or queued work."""

import base64
import re
from email.utils import parseaddr

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Check local booking integration configuration without charges, uploads or emails."

    def handle(self, *args, **options):
        failures = []
        if settings.APP_ENV not in {"staging", "test", "development"}:
            failures.append("Only isolated sandbox environments are supported.")
        if settings.RECOVERY_HOLD:
            failures.append(
                "Recovery hold is active. Reconcile external financial/message effects before lifting it; new booking/payment work is paused."
            )
        if settings.BOOKING_COMPLETION_ENABLED:
            required = [
                settings.BANQUEST_API_SOURCE_KEY,
                settings.BANQUEST_API_PIN,
                settings.BANQUEST_WEBHOOK_KEY,
                settings.RESEND_API_KEY,
                settings.R2_WAIVER_ACCESS_KEY,
                settings.R2_WAIVER_SECRET_KEY,
            ]
            if not all(required) or not settings.BANQUEST_TOKENIZATION_PUBLIC_KEY.startswith("pk_"):
                failures.append(
                    "Install the private sandbox source/PIN/webhook, public tokenization, waiver-storage and booking-mail configuration."
                )
            if (
                not re.fullmatch(r"[a-f0-9]{32}", settings.R2_ACCOUNT_ID)
                or "staging" not in settings.R2_WAIVER_BUCKET
            ):
                failures.append("Use the dedicated private staging waiver bucket/account.")
            try:
                key = settings.RESEND_WEBHOOK_SECRET
                if (
                    not key.startswith("whsec_")
                    or len(base64.b64decode(key[6:] + "=" * (-len(key[6:]) % 4), validate=True))
                    < 16
                ):
                    raise ValueError
            except (TypeError, ValueError):
                failures.append("Install the protected Resend webhook signing secret.")
            if parseaddr(settings.DEFAULT_FROM_EMAIL)[1].casefold() != "bookings@monkeydoplay.com":
                failures.append(
                    "Booking messages require the approved bookings@monkeydoplay.com sender."
                )
        if settings.BACKUP_ENABLED:
            if (
                not settings.R2_BACKUP_READ_ACCESS_KEY
                or not settings.R2_BACKUP_READ_SECRET_KEY
                or "staging" not in settings.R2_BACKUP_BUCKET
                or settings.R2_BACKUP_BUCKET == settings.R2_WAIVER_BUCKET
            ):
                failures.append(
                    "Owner backup downloads require separate Get-only staging backup credentials/bucket."
                )
        if settings.APP_ENV == "staging":
            if connection.vendor != "postgresql":
                failures.append("Staging requires isolated PostgreSQL.")
            else:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT current_user, current_database(), has_table_privilege(current_user,'core_financialposting','SELECT,INSERT'), has_table_privilege(current_user,'core_financialposting','UPDATE'), has_table_privilege(current_user,'core_paymentoperation','UPDATE'), has_table_privilege(current_user,'core_paymentoperation','DELETE')"
                    )
                    row = cursor.fetchone()
                if row != ("monkeydo-functional", "monkeydo_functional", True, False, True, False):
                    failures.append("Use the reviewed least-privileged functional runtime grants.")
        if failures:
            raise CommandError(" ".join(failures))
        self.stdout.write(
            "Local booking configuration checks passed. "
            + (
                "Completed sandbox booking is enabled."
                if settings.BOOKING_COMPLETION_ENABLED
                else "Completed booking remains disabled."
            )
            + " No provider acceptance, charge, storage upload, email delivery or restore is claimed."
        )
