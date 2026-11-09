"""Read-only deployment guard; no provider call, email or database mutation."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from core.models import AccountSecurity, SiteSettings
from core.staging_access import password_current


class Command(BaseCommand):
    help = "Check isolated functional staging configuration and runtime privileges without sending email."

    def handle(self, *args, **options):
        failures = []
        if (
            settings.APP_ENV != "staging"
            or settings.DESIGN_REVIEW_ONLY
            or not settings.CUSTOMER_TEST_BOOKING
        ):
            failures.append("Functional staging flags are required.")
        if (
            settings.DEBUG
            or not settings.SESSION_COOKIE_SECURE
            or not settings.CSRF_COOKIE_SECURE
            or not settings.SECURE_SSL_REDIRECT
        ):
            failures.append("HTTPS and secure session/CSRF cookies are required.")
        if settings.ALLOWED_HOSTS != [
            "testing.monkeydoplay.com"
        ] or settings.CSRF_TRUSTED_ORIGINS != ["https://testing.monkeydoplay.com"]:
            failures.append("Use the isolated testing hostname and origin.")
        if not settings.TRUST_LOCAL_CLIENT_IP or not getattr(
            settings, "SECURE_PROXY_SSL_HEADER", None
        ):
            failures.append(
                "The private local proxy and trusted client-IP configuration must be reviewed."
            )
        if (
            settings.EMAIL_BACKEND != "core.test_email.StagingEmailBackend"
            or not settings.RESEND_API_KEY
            or not settings.STAGING_EMAIL_RECIPIENTS
        ):
            failures.append(
                "Controlled Resend staging credentials and test recipients are required."
            )
        if not password_current(SiteSettings.objects.filter(pk=1).first()):
            failures.append("Set a current private staging password before inviting testers.")
        owners = list(
            get_user_model().objects.filter(is_active=True, is_staff=True, is_superuser=True)
        )
        if len(owners) != 1:
            failures.append("Exactly one active owner account is required.")
        else:
            allowed = {x.casefold() for x in settings.STAGING_EMAIL_RECIPIENTS}
            owner = owners[0]
            addresses = [owner.email]
            secondary = (
                AccountSecurity.objects.filter(user=owner)
                .values_list("secondary_email", flat=True)
                .first()
            )
            if secondary:
                addresses.append(secondary)
            if any(not address or address.casefold() not in allowed for address in addresses):
                failures.append(
                    "Owner and configured recovery emails must be allowlisted test recipients."
                )
        if connection.vendor != "postgresql":
            failures.append("Functional staging requires its isolated PostgreSQL database.")
        else:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(), current_user, has_schema_privilege(current_user, 'public', 'CREATE'), has_table_privilege(current_user, 'django_session', 'INSERT'), rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user"
                )
                row = cursor.fetchone()
            if (
                not row
                or row[0] != "monkeydo_functional"
                or row[1] != "monkeydo-functional"
                or row[2]
                or not row[3]
                or any(row[4:])
            ):
                failures.append(
                    "Use the isolated functional runtime role, with row access and no schema/admin privileges."
                )
        if failures:
            raise CommandError(" ".join(failures))
        self.stdout.write(
            self.style.SUCCESS(
                "Functional staging preflight passed. No emails, provider calls or data changes were made."
            )
        )
