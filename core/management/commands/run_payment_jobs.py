from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from core.payments.jobs import run_one
from core.payments.methods import expire_membership_sources, expire_unused_setups


class Command(BaseCommand):
    help = "Run bounded sandbox payment/reconciliation jobs; never retries uncertain charges."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)

    def handle(self, *args, **options):
        if settings.RECOVERY_HOLD:
            raise CommandError(
                "Recovery review is active; no background financial, card or email work was started."
            )
        limit = options["limit"]
        if not 1 <= limit <= 100:
            raise CommandError("Use a limit between 1 and 100.")
        expire_unused_setups()
        expire_membership_sources()
        if settings.MEMBERSHIP_SALES_ENABLED:
            from core.communications.transport import MailUnavailable
            from core.membership_prompt_emails import prepare_due as prepare_requested
            from core.membership_renewal_notices import prepare_due

            for producer in (prepare_due, prepare_requested):
                try:
                    producer(limit=limit)
                except (DatabaseError, ValidationError, MailUnavailable):
                    self.stderr.write(
                        "Membership reminder preparation needs review; existing queued jobs will continue."
                    )
        completed = 0
        while completed < limit and run_one():
            completed += 1
        self.stdout.write(f"Handled {completed} sandbox jobs. Inspect blocked jobs separately.")
