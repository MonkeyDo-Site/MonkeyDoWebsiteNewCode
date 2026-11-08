from getpass import getpass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from core.staging_access import set_staging_password


class Command(BaseCommand):
    help = "Set the existing shared staging gate interactively for a design-only release. Never accepts a password argument."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="Existing owner username")

    def handle(self, *args, **options):
        if not getattr(settings, "DESIGN_REVIEW_ONLY", False):
            raise CommandError("Use this command only with MONKEYDO_DESIGN_ONLY=1.")
        try:
            owner = get_user_model().objects.get(
                username=options["owner"], is_active=True, is_staff=True, is_superuser=True
            )
        except get_user_model().DoesNotExist:
            raise CommandError(
                "Create the owner account before setting the preview password."
            ) from None
        password = getpass("Shared preview password (hidden): ")
        if password != getpass("Confirm shared preview password (hidden): "):
            raise CommandError("Passwords did not match; no change made.")
        try:
            set_staging_password(owner=owner, password=password)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from None
        self.stdout.write(
            self.style.SUCCESS(
                "Shared preview password saved. No password was printed; prior access tickets are invalid."
            )
        )
