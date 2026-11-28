from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from core.membership_renewal_notices import prepare_due


class Command(BaseCommand):
    help = "Prepare approved due renewal notices; this command sends no email or payment."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        try:
            result = prepare_due(limit=options["limit"], dry_run=options["dry_run"])
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from None
        suffix = (
            "Dry run; no notices were queued."
            if options["dry_run"]
            else "Prepared notices use the existing email queue."
        )
        self.stdout.write(
            f"Examined {result['examined']} due memberships; {result['ready']} eligible notices. {suffix}"
        )
