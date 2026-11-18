"""Closed third-batch staging upgrade; never a general migration runner."""

import io
import json

from django.core.management import BaseCommand, CommandError, call_command
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

from .reviewed_batch_two_schema import guard_database

RUNTIME_ROLE = "monkeydo-functional"
BASELINE = ("core", "0025_customer_referral_source")
REVIEWED = ("core", "0026_owner_feedback_batch_three")


def reviewed_plan():
    executor = MigrationExecutor(connection)
    executor.loader.check_consistent_history(connection)
    if BASELINE not in executor.loader.applied_migrations:
        raise CommandError("The reviewed batch-two baseline must already be applied.")
    if any(
        app == "core" and (app, name) not in executor.loader.disk_migrations
        for app, name in executor.loader.applied_migrations
    ):
        raise CommandError("Database history contains an unknown core migration.")
    plan = [
        (migration.app_label, migration.name, backwards)
        for migration, backwards in executor.migration_plan(executor.loader.graph.leaf_nodes())
    ]
    if plan not in ([], [(*REVIEWED, False)]):
        raise CommandError(
            "Unexpected migration plan. Only reviewed core migration 0026 is allowed."
        )
    return plan


def grant_runtime_access():
    with connection.cursor() as cursor:
        role = connection.ops.quote_name(RUNTIME_ROLE)
        cursor.execute(f"REVOKE ALL ON core_sessionreservationblock FROM {role}")
        cursor.execute(f"GRANT SELECT, INSERT, UPDATE ON core_sessionreservationblock TO {role}")
        cursor.execute(f"REVOKE ALL ON SEQUENCE core_sessionreservationblock_id_seq FROM {role}")
        cursor.execute(
            f"GRANT USAGE, SELECT ON SEQUENCE core_sessionreservationblock_id_seq TO {role}"
        )


class Command(BaseCommand):
    help = "Check the reviewed 0026 plan; --apply uses the separate functional migration identity."

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
            if options["apply"]:
                # PostgreSQL DDL, migration record and runtime grants either all
                # commit or all roll back. A grant failure cannot strand the app.
                with transaction.atomic():
                    call_command(
                        "migrate",
                        "core",
                        REVIEWED[1],
                        interactive=False,
                        stdout=io.StringIO(),
                        verbosity=0,
                    )
                    if reviewed_plan():
                        raise CommandError("Reviewed schema preparation did not complete.")
                    grant_runtime_access()
            self.stdout.write(
                json.dumps(
                    {
                        "pending": [name for app, name, backwards in plan],
                        "applied": [name for app, name, backwards in plan]
                        if options["apply"]
                        else [],
                    }
                )
            )
        finally:
            if locked:
                with connection.cursor() as cursor:
                    cursor.execute("RESET lock_timeout")
                    cursor.execute("RESET statement_timeout")
                    cursor.execute("SELECT pg_advisory_unlock(%s, %s)", [73216, 1])
