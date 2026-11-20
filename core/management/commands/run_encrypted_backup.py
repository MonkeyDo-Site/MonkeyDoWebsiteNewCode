from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from core.backups.services import run_backup
from core.backups.storage import BackupUnavailable


class Command(BaseCommand):
    help = "Create and verify an encrypted offsite staging recovery point; expire only after verification."

    def handle(self, *args, **options):
        try:
            run = run_backup()
        except (ValidationError, BackupUnavailable):
            raise CommandError(
                "Encrypted backup could not be verified. Review the owner Backups page and protected configuration."
            ) from None
        self.stdout.write(f"Backup {run.pk}: {run.get_state_display()}.")
