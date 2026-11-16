"""Closed, release-specific schema plan; invoked by the root deployment controller."""

import io
import json

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

MIGRATION_ROLE = "monkeydo-functional-migrate"
RUNTIME_ROLE = "monkeydo-functional"
REVIEWED = (
    ("core", "0023_owner_feedback_batch_two"),
    ("core", "0024_membership_draft_revisions"),
    ("core", "0025_customer_referral_source"),
)


def guard_database():
    if settings.APP_ENV != "staging" or connection.vendor != "postgresql":
        raise CommandError("Reviewed schema preparation is for functional PostgreSQL staging only.")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_user, current_database(), rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user"
        )
        row = cursor.fetchone()
        if not row or row[:2] != (MIGRATION_ROLE, "monkeydo_functional") or any(row[2:]):
            raise CommandError("Unexpected migration identity or database; no update authorized.")
        cursor.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, has_schema_privilege(rolname, 'public', 'CREATE') FROM pg_roles WHERE rolname=%s",
            [RUNTIME_ROLE],
        )
        runtime = cursor.fetchone()
        if not runtime or any(runtime):
            raise CommandError(
                "Functional runtime role must exist without schema/admin privileges."
            )


def reviewed_plan():
    executor = MigrationExecutor(connection)
    if any(
        app == "core" and (app, name) not in executor.loader.disk_migrations
        for app, name in executor.loader.applied_migrations
    ):
        raise CommandError(
            "Database history contains an unknown core migration; this release cannot prepare it."
        )
    plan = [
        (migration.app_label, migration.name, backwards)
        for migration, backwards in executor.migration_plan(executor.loader.graph.leaf_nodes())
    ]
    allowed = [[(*node, False) for node in REVIEWED[index:]] for index in range(len(REVIEWED) + 1)]
    if plan not in allowed:
        raise CommandError(
            "Unexpected migration plan. Only reviewed core migrations 0023–0025 are allowed."
        )
    return plan


def grant_runtime_access():
    # These identifiers are constants, never operator-supplied SQL.
    with connection.cursor() as cursor:
        role = connection.ops.quote_name(RUNTIME_ROLE)
        cursor.execute(
            f"REVOKE DELETE, TRUNCATE, REFERENCES, TRIGGER ON core_ownernotice FROM {role}"
        )
        cursor.execute(
            f"REVOKE UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON core_membershipdraftrevision FROM {role}"
        )
        cursor.execute(f"GRANT SELECT, INSERT, UPDATE ON core_ownernotice TO {role}")
        cursor.execute(f"GRANT SELECT, INSERT ON core_membershipdraftrevision TO {role}")
        cursor.execute(
            f"GRANT USAGE, SELECT ON SEQUENCE core_ownernotice_id_seq, core_membershipdraftrevision_id_seq TO {role}"
        )


class Command(BaseCommand):
    help = "Check the reviewed 0023–0025 plan; --apply requires the separate functional migration identity."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        guard_database()
        locked = False
        try:
            if options["apply"]:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", [73216, 1])
                    locked = cursor.fetchone()[0]
                    if not locked:
                        raise CommandError(
                            "Calendar is busy; no schema update started. Retry later."
                        )
                    cursor.execute("SET lock_timeout = '10s'")
                    cursor.execute("SET statement_timeout = '60s'")
            plan = reviewed_plan()
            # This command selects explicit legacy columns and works before 0025 exists.
            email_report = io.StringIO()
            try:
                call_command("check_customer_emails", stdout=email_report)
            except CommandError as error:
                raise CommandError(email_report.getvalue().strip() + " " + str(error)) from error
            applied = []
            if options["apply"]:
                call_command(
                    "migrate",
                    "core",
                    REVIEWED[-1][1],
                    interactive=False,
                    stdout=io.StringIO(),
                    verbosity=0,
                )
                if reviewed_plan():
                    raise CommandError("Reviewed schema preparation did not complete.")
                grant_runtime_access()
                applied = [name for app, name, backwards in plan]
            self.stdout.write(
                json.dumps({"pending": [name for app, name, backwards in plan], "applied": applied})
            )
        finally:
            if locked:
                with connection.cursor() as cursor:
                    cursor.execute("RESET lock_timeout")
                    cursor.execute("RESET statement_timeout")
                    cursor.execute("SELECT pg_advisory_unlock(%s, %s)", [73216, 1])
