from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.availability import NEW_YORK
from core.models import Session, SiteSettings


class Command(BaseCommand):
    help = "Create only artificial session data; safe to rerun without clearing existing work."

    @transaction.atomic
    def handle(self, *args, **options):
        if settings.APP_ENV not in {"development", "test", "staging"}:
            raise CommandError("Test environments only.")
        SiteSettings.objects.get_or_create(pk=1)
        count = 0
        for offset in range(12):
            day = timezone.localdate() + timedelta(days=offset)
            if day.weekday() == 5:
                continue
            for hour, minute in [(11, 30), (13, 0), (14, 30), (16, 0)]:
                start = datetime.combine(day, time(hour, minute), NEW_YORK)
                _, created = Session.objects.get_or_create(
                    starts_at=start,
                    defaults={"ends_at": start + timedelta(minutes=75), "public": True},
                )
                count += created
        self.stdout.write(
            self.style.SUCCESS(f"Created {count} test sessions. Existing records preserved.")
        )
