from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

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
            from core.membership_renewal_notices import prepare_due

            prepare_due(limit=limit)
        completed = 0
        while completed < limit and run_one():
            completed += 1
        self.stdout.write(f"Handled {completed} sandbox jobs. Inspect blocked jobs separately.")
