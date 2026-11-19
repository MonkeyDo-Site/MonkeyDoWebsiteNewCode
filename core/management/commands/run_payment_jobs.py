from django.core.management.base import BaseCommand, CommandError

from core.payments.jobs import run_one


class Command(BaseCommand):
    help = "Run bounded sandbox payment/reconciliation jobs; never retries uncertain charges."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 100:
            raise CommandError("Use a limit between 1 and 100.")
        completed = 0
        while completed < limit and run_one():
            completed += 1
        self.stdout.write(f"Handled {completed} sandbox jobs. Inspect blocked jobs separately.")
