import json

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from core.membership_collection_plan import review_due


class Command(BaseCommand):
    help = "Preview membership installment eligibility and credit arithmetic; creates no payment."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--include-overdue", action="store_true")

    def handle(self, *args, **options):
        try:
            plan = review_due(limit=options["limit"], include_overdue=options["include_overdue"])
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from None
        self.stdout.write(json.dumps(plan, sort_keys=True))
