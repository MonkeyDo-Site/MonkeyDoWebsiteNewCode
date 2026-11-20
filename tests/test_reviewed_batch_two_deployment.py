import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from unittest import TestCase, skipUnless
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from core.management.commands import reviewed_batch_two_schema as schema
from deploy import monkeydo_deploy as deploy
from tests.test_deployment import FakeHost

ROOT = Path(__file__).resolve().parents[1]


class ReviewedDeploymentTests(TestCase):
    def setUp(self):
        deploy.select_target("functional")

    def tearDown(self):
        deploy.select_target("design")

    def test_hash_mismatch_refuses_candidate_before_any_service_or_database_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory)
            shutil.copytree(ROOT / "core/migrations", candidate / "core/migrations")
            migration = candidate / "core/migrations/0023_owner_feedback_batch_two.py"
            migration.write_text(migration.read_text() + "\n# modified migration")
            host = deploy.Host({}, candidate / "private.log")
            with patch.object(deploy.Host, "command") as command:
                with self.assertRaisesRegex(deploy.DeployError, "checksum mismatch"):
                    host.reviewed_batch_two(candidate, "a" * 40)
                command.assert_not_called()

    def test_preflight_failure_never_stops_the_website_or_creates_checkpoint(self):
        host = deploy.Host({}, Path("/tmp/unused"))
        with (
            patch.object(deploy.Host, "command", side_effect=deploy.DeployError("duplicates")),
            patch.object(host, "schema_checkpoint") as backup,
            self.assertRaises(deploy.DeployError),
        ):
            host.reviewed_batch_two(ROOT, "a" * 40)
        backup.assert_not_called()

    def test_backup_or_migration_failure_restarts_and_verifies_existing_service(self):
        for failure in ("backup", "migration"):
            with self.subTest(failure=failure):
                calls = []
                host = deploy.Host({"POSTGRES_USER": "monkeydo-functional"}, Path("/tmp/unused"))

                def command(instance, args, **kwargs):
                    calls.append((args, kwargs, instance.environment))
                    if "--apply" in args:
                        raise deploy.DeployError("migration failed")
                    return '{"pending":["0023"],"applied":[]}'

                with (
                    patch.object(deploy.Host, "command", autospec=True, side_effect=command),
                    patch.object(
                        host,
                        "schema_checkpoint",
                        side_effect=deploy.DeployError("backup failed")
                        if failure == "backup"
                        else None,
                        return_value=Path("/private/checkpoint.dump"),
                    ),
                    patch.object(host, "healthy") as health,
                    self.assertRaisesRegex(
                        deploy.DeployError, "existing release was restarted and verified"
                    ),
                ):
                    host.reviewed_batch_two(ROOT, "a" * 40)
                self.assertIn(
                    ["systemctl", "stop", "monkeydo-functional.service"],
                    [args for args, kwargs, env in calls],
                )
                self.assertEqual(
                    calls[-1][0], ["systemctl", "start", "monkeydo-functional.service"]
                )
                health.assert_called_once()
                migrations = [
                    (args, kwargs, env)
                    for args, kwargs, env in calls
                    if "reviewed_batch_two_schema" in args
                ]
                self.assertTrue(
                    all(
                        kwargs["user"] == "monkeydo-functional-migrate"
                        and env["POSTGRES_USER"] == "monkeydo-functional-migrate"
                        for args, kwargs, env in migrations
                    )
                )
                if failure == "backup":
                    self.assertFalse(any("--apply" in args for args, kwargs, env in calls))

    def test_approved_operation_orders_preflight_backup_migrations_then_service_recovery(self):
        calls = []
        host = deploy.Host({}, Path("/tmp/unused"))

        def command(instance, args, **kwargs):
            if "reviewed_batch_two_schema" in args:
                calls.append("apply" if "--apply" in args else "preflight")
                return '{"pending":["0023"],"applied":["0023"]}'
            calls.append(args[1])
            return ""

        with (
            patch.object(deploy.Host, "command", autospec=True, side_effect=command),
            patch.object(
                host,
                "schema_checkpoint",
                side_effect=lambda commit: (
                    calls.append("backup") or Path("/private/checkpoint.dump")
                ),
            ),
            patch.object(host, "healthy", side_effect=lambda: calls.append("healthy")),
        ):
            result = host.reviewed_batch_two(ROOT, "a" * 40)
        self.assertEqual(calls, ["preflight", "stop", "backup", "apply", "start", "healthy"])
        self.assertEqual(result["applied"], ["0023"])

    def test_schema_plan_rejects_unreviewed_or_reverse_migrations(self):
        from types import SimpleNamespace

        for plan in (
            [(SimpleNamespace(app_label="core", name="0026_future"), False)],
            [(SimpleNamespace(app_label="core", name=schema.REVIEWED[-1][1]), True)],
        ):
            with patch.object(schema, "MigrationExecutor") as executor:
                executor.return_value.migration_plan.return_value = plan
                with self.assertRaises(CommandError):
                    schema.reviewed_plan()
        with patch.object(schema, "MigrationExecutor") as executor:
            executor.return_value.loader.applied_migrations = {("core", "0099_unreviewed"): None}
            executor.return_value.loader.disk_migrations = {}
            with self.assertRaisesRegex(CommandError, "unknown core migration"):
                schema.reviewed_plan()

    def test_recovery_checkpoint_is_persisted_before_reviewed_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            state_file = Path(directory) / "state.json"
            outer = self

            class ScopedHost(FakeHost):
                def prepare(self, *args, **kwargs):
                    outer.assertTrue(kwargs["reviewed_batch_two"])
                    outer.assertEqual(
                        json.loads(state_file.read_text())["pending"]["release"], "/old"
                    )
                    return super().prepare(*args)

            host = ScopedHost()
            host.fail_build = True
            controller = deploy.Controller(host, state_file)
            with self.assertRaises(deploy.DeployError):
                controller.deploy(Path("/fixture.zip"), "0" * 64, "a" * 40, reviewed_batch_two=True)
            self.assertIsNone(json.loads(state_file.read_text())["pending"])
            self.assertEqual(host.current["release"], "/old")


@skipUnless(connection.vendor == "postgresql", "Reviewed schema integration requires PostgreSQL.")
class ReviewedSchemaIntegrationTests(TransactionTestCase):
    def test_upgrade_preserves_legacy_data_rejects_duplicates_and_is_repeatable(self):
        runtime_role = "mdo_batch_two_test_" + uuid.uuid4().hex[:12]
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE "{runtime_role}" NOLOGIN')
        try:
            executor = MigrationExecutor(connection)
            executor.migrate([("core", "0022_weekly_default_archive")])
            legacy = executor.loader.project_state([("core", "0022_weekly_default_archive")]).apps
            customer_model = legacy.get_model("core", "Customer")
            first = customer_model.objects.create(
                last_name="Original", phone="2025550100", email="SAME@example.invalid"
            )
            second = customer_model.objects.create(
                last_name="Other", phone="2025550101", email="same@example.invalid"
            )
            old_snapshot = list(customer_model.objects.order_by("pk").values())
            from datetime import timedelta

            from django.utils import timezone

            session = legacy.get_model("core", "Session").objects.create(
                starts_at=timezone.now(),
                ends_at=timezone.now() + timedelta(minutes=75),
                public=False,
            )
            booking = legacy.get_model("core", "Booking").objects.create(
                customer_id=first.pk, session_id=session.pk, children=2, adults=1
            )
            policy = legacy.get_model("core", "PricingPolicy").objects.create()
            quote = legacy.get_model("core", "BookingQuote").objects.create(
                booking_id=booking.pk, policy_id=policy.pk, revision=1, snapshot={"total": "30.00"}
            )
            booking_before = legacy.get_model("core", "Booking").objects.values().get(pk=booking.pk)
            quote_before = (
                legacy.get_model("core", "BookingQuote").objects.values().get(pk=quote.pk)
            )
            actor = legacy.get_model("auth", "User").objects.create(username="checkpoint-owner")
            prices = legacy.get_model("core", "MembershipPricing").objects.create()
            draft = legacy.get_model("core", "MembershipDraft").objects.create(
                customer_id=first.pk,
                kind="subscription",
                places=1,
                months=3,
                billing="monthly",
                starts_on=session.starts_at.date(),
                ends_on=session.starts_at.date() + timedelta(days=89),
                unit_price="17.99",
                pricing_id=prices.pk,
                fee_policy_id=policy.pk,
                expected_method="cash",
                snapshot={"test_mode": True},
                creation_key=uuid.uuid4(),
                actor_id=actor.pk,
            )
            cycle = legacy.get_model("core", "MembershipDraftCycle").objects.create(
                draft_id=draft.pk,
                number=1,
                starts_on=draft.starts_on,
                ends_on=draft.ends_on,
                charge_on=draft.starts_on,
                quote={"total": "17.99"},
            )
            draft_before = (
                legacy.get_model("core", "MembershipDraft").objects.values().get(pk=draft.pk)
            )
            cycle_before = (
                legacy.get_model("core", "MembershipDraftCycle").objects.values().get(pk=cycle.pk)
            )

            def historical_executor(database):
                # Exercise the frozen batch-two release graph, not the newer 0026 release.
                executor = MigrationExecutor(database)
                nodes = [node for node in executor.loader.graph.leaf_nodes() if node[0] != "core"]
                nodes.append(schema.REVIEWED[-1])
                executor.loader.graph.leaf_nodes = lambda app=None: [
                    node for node in nodes if app is None or node[0] == app
                ]
                return executor

            with (
                patch.object(schema, "MigrationExecutor", side_effect=historical_executor),
                patch.object(schema, "guard_database"),
                patch.object(schema, "RUNTIME_ROLE", runtime_role),
            ):
                with self.assertRaises(CommandError):
                    call_command("reviewed_batch_two_schema", stdout=io.StringIO())
                self.assertEqual(list(customer_model.objects.order_by("pk").values()), old_snapshot)
                self.assertNotIn(
                    "referral_source",
                    {
                        c.name
                        for c in connection.introspection.get_table_description(
                            connection.cursor(), "core_customer"
                        )
                    },
                )
                second.email = "other@example.invalid"
                second.save()
                output = io.StringIO()
                call_command("reviewed_batch_two_schema", stdout=output)
                self.assertEqual(len(json.loads(output.getvalue())["pending"]), 3)
                call_command("reviewed_batch_two_schema", apply=True, stdout=io.StringIO())
                call_command("reviewed_batch_two_schema", apply=True, stdout=io.StringIO())
            # Inspect that historical release's schema; runtime Booking now
            # has the later workflow-provenance column, absent at 0025.
            reviewed_apps = (
                MigrationExecutor(connection).loader.project_state([schema.REVIEWED[-1]]).apps
            )
            Booking = reviewed_apps.get_model("core", "Booking")
            BookingQuote = reviewed_apps.get_model("core", "BookingQuote")
            Customer = reviewed_apps.get_model("core", "Customer")
            MembershipDraft = reviewed_apps.get_model("core", "MembershipDraft")
            MembershipDraftCycle = reviewed_apps.get_model("core", "MembershipDraftCycle")

            self.assertEqual(Customer.objects.get(pk=first.pk).email, "SAME@example.invalid")
            self.assertEqual(Customer.objects.get(pk=first.pk).referral_source, "")
            self.assertEqual(Customer.objects.count(), 2)
            self.assertEqual(Booking.objects.values().get(pk=booking.pk), booking_before)
            self.assertEqual(BookingQuote.objects.values().get(pk=quote.pk), quote_before)
            self.assertEqual(MembershipDraft.objects.values().get(pk=draft.pk), draft_before)
            self.assertEqual(MembershipDraftCycle.objects.values().get(pk=cycle.pk), cycle_before)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege(%s, 'core_ownernotice', 'SELECT,INSERT,UPDATE'), has_table_privilege(%s, 'core_membershipdraftrevision', 'SELECT,INSERT'), has_schema_privilege(%s, 'public', 'CREATE')",
                    [runtime_role] * 3,
                )
                self.assertEqual(cursor.fetchone(), (True, True, False))
        finally:
            # Keep the disposable test database at the current schema for later tests.
            MigrationExecutor(connection).migrate(
                MigrationExecutor(connection).loader.graph.leaf_nodes()
            )
            with connection.cursor() as cursor:
                cursor.execute(f'DROP OWNED BY "{runtime_role}"')
                cursor.execute(f'DROP ROLE "{runtime_role}"')

    def test_live_identity_guard_refuses_the_test_database_and_user(self):
        from django.test import override_settings

        with override_settings(APP_ENV="staging"), self.assertRaises(CommandError):
            call_command("reviewed_batch_two_schema", stdout=io.StringIO())

    def test_private_checkpoint_can_be_restored_into_a_new_disposable_database(self):
        from core.models import Customer

        tools = {}
        for name in ("pg_dump", "pg_restore"):
            path = shutil.which(name)
            if not path:
                try:
                    import pgserver

                    path = str(Path(pgserver.__file__).parent / "pginstall/bin" / name)
                except ImportError:
                    self.skipTest("Matching PostgreSQL dump/restore tools unavailable.")
            tools[name] = path
        version = subprocess.run(
            [tools["pg_dump"], "--version"], capture_output=True, text=True, check=True
        )
        match = re.search(r"(\d+)\.", version.stdout)
        if not match or int(match[1]) < connection.pg_version // 10000:
            self.skipTest(
                "Host pg_dump is older than the test server; actual restore is verified locally with matching tools."
            )
        row = Customer.objects.create(
            last_name="Checkpoint fixture", phone="2025550170", email="checkpoint@example.invalid"
        )
        options = connection.settings_dict
        routing = ["--host", options["HOST"], "--username", options["USER"]]
        if options["PORT"]:
            routing += ["--port", str(options["PORT"])]
        native_run = subprocess.run

        def translated(args, **kwargs):
            if "/usr/bin/pg_dump" in args:
                args = [tools["pg_dump"], *routing, "--format=custom", "--dbname", options["NAME"]]
                kwargs["env"] = dict(kwargs.get("env", {}), PGPASSWORD=options["PASSWORD"])
            elif args[0] == "/usr/bin/pg_restore":
                args = [tools["pg_restore"], *args[1:]]
            return native_run(args, **kwargs)

        recovered = "mdo_b2_restore_" + uuid.uuid4().hex[:12]
        deploy.select_target("functional")
        try:
            with tempfile.TemporaryDirectory() as directory:
                state = Path(directory)
                with (
                    patch.object(deploy, "STATE", state),
                    patch.object(deploy, "BASE", state),
                    patch.object(deploy.subprocess, "run", side_effect=translated),
                ):
                    backup = deploy.Host({}, state / "private.log").schema_checkpoint("a" * 40)
                self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
                self.assertEqual(backup.parent.stat().st_mode & 0o777, 0o700)
                self.assertTrue(
                    json.loads(backup.with_suffix(".json").read_text())[
                        "archive_catalogue_verified"
                    ]
                )
                with connection.cursor() as cursor:
                    cursor.execute(f'CREATE DATABASE "{recovered}"')
                try:
                    restored = native_run(
                        [
                            tools["pg_restore"],
                            *routing,
                            "--clean",
                            "--if-exists",
                            "--no-owner",
                            "--no-privileges",
                            "--exit-on-error",
                            "--dbname",
                            recovered,
                            str(backup),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=60,
                        env=dict(os.environ, PGPASSWORD=options["PASSWORD"]),
                    )
                    self.assertEqual(restored.returncode, 0, restored.stderr)
                    import psycopg

                    with psycopg.connect(
                        dbname=recovered,
                        user=options["USER"],
                        password=options["PASSWORD"],
                        host=options["HOST"],
                        port=options["PORT"] or 5432,
                    ) as recovery:
                        self.assertEqual(
                            recovery.execute(
                                "SELECT last_name, email FROM core_customer WHERE id=%s", [row.pk]
                            ).fetchone(),
                            (row.last_name, row.email),
                        )
                finally:
                    with connection.cursor() as cursor:
                        cursor.execute(f'DROP DATABASE "{recovered}"')
        finally:
            deploy.select_target("design")
