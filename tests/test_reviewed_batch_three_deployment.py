"""Release-specific migration, least privileges and compatible code recovery."""

import io
import json
import shutil
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest import TestCase, skipUnless
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from core.management.commands import reviewed_batch_three_schema as schema
from deploy import monkeydo_deploy as deploy
from tests.test_deployment import FakeHost

ROOT = Path(__file__).resolve().parents[1]


class ThirdBatchDeploymentTests(TestCase):
    def setUp(self):
        deploy.select_target("functional")

    def tearDown(self):
        deploy.select_target("design")

    def test_checksum_and_target_fail_before_database_or_service_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            candidate = Path(folder)
            shutil.copytree(ROOT / "core/migrations", candidate / "core/migrations")
            migration = candidate / "core/migrations/0026_owner_feedback_batch_three.py"
            migration.write_text(migration.read_text() + "\n# changed")
            host = deploy.Host({}, candidate / "log")
            with patch.object(host, "command") as command:
                with self.assertRaisesRegex(deploy.DeployError, "checksum"):
                    host.reviewed_batch_three(candidate, "a" * 40)
                deploy.select_target("design")
                with self.assertRaisesRegex(deploy.DeployError, "Functional-only"):
                    host.reviewed_batch_three(ROOT, "a" * 40)
                command.assert_not_called()

    def test_preflight_backup_and_apply_failures_keep_existing_release(self):
        for failure in ("preflight", "backup", "apply", None):
            with self.subTest(failure=failure):
                calls = []
                host = deploy.Host({}, Path("/tmp/unused"))

                def command(instance, args, **kwargs):
                    stage = args[1]
                    if "reviewed_batch_three_schema" in args:
                        stage = "apply" if "--apply" in args else "preflight"
                        self.assertEqual(kwargs["user"], "monkeydo-functional-migrate")
                        self.assertEqual(instance.environment["POSTGRES_USER"], kwargs["user"])
                    calls.append(stage)
                    if failure == stage:
                        raise deploy.DeployError("fixture failure")
                    return '{"pending":["0026"],"applied":["0026"]}'

                def backup(commit):
                    calls.append("backup")
                    if failure == "backup":
                        raise deploy.DeployError("backup failed")
                    return Path("/private/checkpoint.dump")

                with (
                    patch.object(deploy.Host, "command", autospec=True, side_effect=command),
                    patch.object(host, "schema_checkpoint", side_effect=backup),
                    patch.object(host, "healthy", side_effect=lambda: calls.append("healthy")),
                ):
                    if failure:
                        with self.assertRaises(deploy.DeployError):
                            host.reviewed_batch_three(ROOT, "a" * 40)
                    else:
                        result = host.reviewed_batch_three(ROOT, "a" * 40)
                        self.assertEqual(result["applied"], ["0026"])
                expected = ["preflight"]
                if failure != "preflight":
                    expected += ["stop", "backup"]
                    if failure != "backup":
                        expected.append("apply")
                    expected += ["start", "healthy"]
                self.assertEqual(calls, expected)

    def test_recovery_is_persisted_before_third_batch_schema_preparation(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            outer = self

            class ScopedHost(FakeHost):
                def prepare(self, *args, **kwargs):
                    outer.assertEqual(kwargs, {"reviewed_batch_three": True})
                    outer.assertEqual(json.loads(state.read_text())["pending"]["release"], "/old")
                    return super().prepare(*args)

            host = ScopedHost()
            host.fail_build = True
            with self.assertRaises(deploy.DeployError):
                deploy.Controller(host, state).deploy(
                    Path("/fixture.zip"), "0" * 64, "a" * 40, reviewed_batch_three=True
                )
            self.assertIsNone(json.loads(state.read_text())["pending"])
            self.assertEqual(host.current["release"], "/old")

    def test_old_code_compatibility_guard_and_refused_switch_keep_pointer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("old", "current"):
                (root / "releases" / name).mkdir(parents=True)
                (root / "releases" / name / "manage.py").touch()
            (root / "staging").mkdir()
            (root / "staging/current").symlink_to(root / "releases/current")
            host = deploy.Host({}, root / "log")
            for answers, accepted in (
                (["f"], True),
                (["t", "f"], True),
                (["t", "t"], False),
                (["unknown"], False),
            ):
                with patch.object(host, "command", side_effect=["f"] + answers):
                    if accepted:
                        host.ensure_compatible_release(root / "releases/old")
                    else:
                        with self.assertRaises(deploy.DeployError):
                            host.ensure_compatible_release(root / "releases/old")
            # A current compatible release is accepted without DB access.
            with patch.object(host, "command") as command:
                host.ensure_compatible_release(ROOT)
                command.assert_not_called()
            with (
                patch.object(deploy, "BASE", root),
                patch.object(deploy, "DROPIN", root / "dropin"),
                patch.object(
                    host, "ensure_compatible_release", side_effect=deploy.DeployError("blocked")
                ),
                patch.object(host, "command") as command,
                self.assertRaisesRegex(deploy.DeployError, "blocked"),
            ):
                host.switch({"release": str(root / "releases/old"), "dropin": None})
            self.assertEqual((root / "staging/current").resolve(), root / "releases/current")
            self.assertEqual(
                [call.args[0] for call in command.call_args_list],
                [
                    ["systemctl", "stop", deploy.UNIT],
                    ["systemctl", "start", deploy.UNIT],
                ],
            )

    def test_schema_plan_refuses_missing_baseline_future_reverse_and_unknown_history(self):
        from types import SimpleNamespace

        migration = SimpleNamespace(app_label="core", name=schema.REVIEWED[1])
        for applied, plan in (
            ({}, [(migration, False)]),
            ({schema.BASELINE: None}, [(migration, True)]),
            (
                {schema.BASELINE: None},
                [(SimpleNamespace(app_label="core", name="0027_future"), False)],
            ),
            ({schema.BASELINE: None, ("core", "0099_unknown"): None}, []),
        ):
            with patch.object(schema, "MigrationExecutor") as executor:
                executor.return_value.loader.applied_migrations = applied
                executor.return_value.loader.disk_migrations = {
                    schema.BASELINE: None,
                    schema.REVIEWED: None,
                }
                executor.return_value.migration_plan.return_value = plan
                with self.assertRaises(CommandError):
                    schema.reviewed_plan()


@skipUnless(connection.vendor == "postgresql", "Reviewed upgrade requires PostgreSQL.")
class ThirdBatchSchemaIntegrationTests(TransactionTestCase):
    def test_real_upgrade_preserves_rows_grants_only_needed_access_and_is_repeatable(self):
        role = "mdo_b3_test_" + uuid.uuid4().hex[:12]
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE "{role}" NOLOGIN')
        try:
            executor = MigrationExecutor(connection)
            executor.migrate([schema.BASELINE])
            legacy = executor.loader.project_state([schema.BASELINE]).apps
            Customer = legacy.get_model("core", "Customer")
            Session = legacy.get_model("core", "Session")
            Booking = legacy.get_model("core", "Booking")
            customer = Customer.objects.create(
                last_name="Preserved", phone="2025550175", email="kept@example.invalid"
            )
            starts = timezone.now()
            session = Session.objects.create(
                starts_at=starts, ends_at=starts + timedelta(minutes=75)
            )
            booking = Booking.objects.create(
                customer_id=customer.pk, session_id=session.pk, children=2, adults=1
            )
            policy = legacy.get_model("core", "PricingPolicy").objects.create()
            quote = legacy.get_model("core", "BookingQuote").objects.create(
                booking_id=booking.pk, policy_id=policy.pk, revision=1, snapshot={"total": "30.00"}
            )
            models = [
                (Customer, customer.pk),
                (Session, session.pk),
                (Booking, booking.pk),
                (type(quote), quote.pk),
            ]
            before = [model.objects.values().get(pk=pk) for model, pk in models]

            def historical_executor(database):
                # Test the closed 0026 release against its own graph, not newer
                # payment migrations that the historical command must reject.
                frozen = MigrationExecutor(database)
                nodes = [node for node in frozen.loader.graph.leaf_nodes() if node[0] != "core"]
                nodes.append(schema.REVIEWED)
                frozen.loader.graph.leaf_nodes = lambda app=None: [
                    node for node in nodes if app is None or node[0] == app
                ]
                return frozen

            with (
                patch.object(schema, "MigrationExecutor", side_effect=historical_executor),
                patch.object(schema, "guard_database"),
                patch.object(schema, "RUNTIME_ROLE", role),
            ):
                output = io.StringIO()
                call_command("reviewed_batch_three_schema", stdout=output)
                self.assertEqual(json.loads(output.getvalue())["pending"], [schema.REVIEWED[1]])
                # Preflight performs no DDL. A grant failure must undo all DDL too.
                with (
                    patch.object(
                        schema, "grant_runtime_access", side_effect=CommandError("grant failed")
                    ),
                    self.assertRaisesRegex(CommandError, "grant failed"),
                ):
                    call_command("reviewed_batch_three_schema", apply=True, stdout=io.StringIO())
                with connection.cursor() as cursor:
                    cursor.execute("SELECT to_regclass('core_sessionreservationblock')")
                    self.assertIsNone(cursor.fetchone()[0])
                self.assertEqual(schema.reviewed_plan(), [(*schema.REVIEWED, False)])
                call_command("reviewed_batch_three_schema", apply=True, stdout=io.StringIO())
                call_command("reviewed_batch_three_schema", apply=True, stdout=io.StringIO())
            after = [model.objects.values().get(pk=pk) for model, pk in models]
            self.assertEqual(before, after)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT has_table_privilege(%s, 'core_sessionreservationblock', 'SELECT,INSERT,UPDATE'), has_table_privilege(%s, 'core_sessionreservationblock', 'DELETE'), has_sequence_privilege(%s, 'core_sessionreservationblock_id_seq', 'USAGE,SELECT'), has_schema_privilege(%s, 'public', 'CREATE')",
                    [role] * 4,
                )
                self.assertEqual(cursor.fetchone(), (True, False, True, False))
            # Real DB state drives the older-code recovery guard.
            deploy.select_target("functional")
            host = deploy.Host({}, Path("/tmp/unused"))

            def query(args):
                with connection.cursor() as cursor:
                    cursor.execute(args[-1])
                    return "t" if cursor.fetchone()[0] else "f"

            with (
                tempfile.TemporaryDirectory() as older,
                patch.object(host, "command", side_effect=query),
            ):
                host.ensure_compatible_release(Path(older))
                from core.models import CalendarDate

                CalendarDate.objects.create(day=starts.date(), backend_only=True)
                with self.assertRaisesRegex(deploy.DeployError, "Older code"):
                    host.ensure_compatible_release(Path(older))
        finally:
            deploy.select_target("design")
            MigrationExecutor(connection).migrate(
                MigrationExecutor(connection).loader.graph.leaf_nodes()
            )
            with connection.cursor() as cursor:
                cursor.execute(f'DROP OWNED BY "{role}"')
                cursor.execute(f'DROP ROLE "{role}"')

    def test_host_identity_guard_rejects_local_test_database(self):
        with self.assertRaises(CommandError):
            call_command("reviewed_batch_three_schema", stdout=io.StringIO())
