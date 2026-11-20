from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from core.waivers.services import expire_evidence
from core.waivers.storage import EvidenceUnavailable


class Command(BaseCommand):
    help = "Delete expired private waiver files only; retain minimal signing metadata and audit."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        try:
            count = expire_evidence(limit=options["limit"])
        except (ValidationError, EvidenceUnavailable):
            raise CommandError(
                "Waiver retention could not be confirmed. Review private storage configuration and outstanding evidence removals."
            ) from None
        self.stdout.write(
            f"Removed {count} expired waiver evidence files; historical metadata retained."
        )
