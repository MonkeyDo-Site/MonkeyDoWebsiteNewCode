from getpass import getpass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from core.staging_access import set_staging_password


class Command(BaseCommand):
    help = "Set the functional-test access gate interactively without printing its password."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True)

    def handle(self, *args, **options):
        if (
            settings.DESIGN_REVIEW_ONLY
            or not settings.CUSTOMER_TEST_BOOKING
            or settings.APP_ENV not in {"staging", "test"}
        ):
            raise CommandError("Use this command only in isolated functional staging.")
        try:
            owner = get_user_model().objects.get(
                username=options["owner"], is_active=True, is_staff=True, is_superuser=True
            )
        except get_user_model().DoesNotExist:
            raise CommandError("Create the owner account first.") from None
        password = getpass("Functional staging password (hidden): ")
        if password != getpass("Confirm functional staging password (hidden): "):
            raise CommandError("Passwords did not match; no change made.")
        try:
            set_staging_password(owner=owner, password=password)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from None
        self.stdout.write(
            self.style.SUCCESS("Functional staging password saved. No password was printed.")
        )
