"""Read-only pre-migration check. No contact addresses are printed."""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.db.models.functions import Lower

from core.models import Customer


class Command(BaseCommand):
    help = "Check current email uniqueness before migration 0023. Never changes customer data."

    def handle(self, *args, **options):
        duplicates = list(
            Customer.objects.exclude(email="")
            .annotate(normalized_email=Lower("email"))
            .values("normalized_email")
            .annotate(total=Count("pk"))
            .filter(total__gt=1)
        )
        if duplicates:
            for group in duplicates:
                ids = list(
                    Customer.objects.filter(email__iexact=group["normalized_email"]).values_list(
                        "pk", flat=True
                    )
                )
                self.stdout.write("Conflicting customer IDs: " + ", ".join(str(pk) for pk in ids))
            raise CommandError(
                "Current email duplicates need owner review before deployment. No customers or addresses were modified."
            )
        self.stdout.write(
            self.style.SUCCESS(
                "Current customer email uniqueness check passed. No data was changed."
            )
        )
