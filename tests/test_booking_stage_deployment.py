"""Closed booking-stage upgrade, row preservation, least privilege and code recovery."""

import io
import json
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone

from core.management.commands import reviewed_booking_completion_schema as schema
from deploy import monkeydo_deploy as deploy

ROOT = Path(__file__).resolve().parents[1]


class ClosedBookingPlanTests(SimpleTestCase):
    def test_only_exact_forward_suffixes_are_allowed(self):
        for names in [list(schema.REVIEWED_NAMES), list(schema.REVIEWED_NAMES[8:]), []]:
            executor = MagicMock()
            executor.loader.applied_migrations = {schema.BASELINE: None}
            executor.loader.disk_migrations = {schema.BASELINE: None}
            executor.migration_plan.return_value = [
                (SimpleNamespace(app_label="core", name=name), False) for name in names
            ]
            with patch.object(schema, "MigrationExecutor", return_value=executor):
                self.assertEqual([name for app, name, backwards in schema.reviewed_plan()], names)
        for names, reverse in [
            (["0099_unreviewed"], False),
            ([schema.REVIEWED_NAMES[0]], True),
            ([schema.REVIEWED_NAMES[0]], False),
        ]:
            executor.migration_plan.return_value = [
                (SimpleNamespace(app_label="core", name=name), reverse) for name in names
            ]
            with (
                patch.object(schema, "MigrationExecutor", return_value=executor),
                self.assertRaises(CommandError),
            ):
                schema.reviewed_plan()

    def test_root_helper_checksums_exact_reviewed_migrations_and_units(self):
        import hashlib

        self.assertEqual(
            set(deploy.BOOKING_MIGRATIONS), {name + ".py" for name in schema.REVIEWED_NAMES}
        )
        for name, digest in deploy.BOOKING_MIGRATIONS.items():
            self.assertEqual(
                hashlib.sha256((ROOT / "core/migrations" / name).read_bytes()).hexdigest(), digest
            )
        for name, digest in deploy.BOOKING_UNITS.items():
            self.assertEqual(
                hashlib.sha256((ROOT / "deploy" / name).read_bytes()).hexdigest(), digest
            )
        self.assertEqual(len(deploy.BOOKING_UNITS), 6)

    def test_older_code_is_refused_when_new_workflow_records_exist(self):
        deploy.select_target("functional")
        self.addCleanup(deploy.select_target, "design")
        host = deploy.Host({}, Path("/tmp/unused-booking-compatibility.log"))
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(host, "command", side_effect=["t", "t"]),
            self.assertRaisesRegex(deploy.DeployError, "older release"),
        ):
            host.ensure_compatible_release(Path(directory))
        with patch.object(host, "command") as command:
            host.ensure_compatible_release(ROOT)
            command.assert_not_called()

    def test_design_target_refuses_reviewed_booking_before_services_or_database(self):
        deploy.select_target("design")
        host = deploy.Host({}, Path("/tmp/unused-booking-target.log"))
        with (
            patch.object(host, "command") as command,
            self.assertRaisesRegex(deploy.DeployError, "Functional-only"),
        ):
            host.reviewed_booking(ROOT, "a" * 40)
        command.assert_not_called()

    def test_old_booking_release_cannot_hide_accepted_visit_credit(self):
        deploy.select_target("functional")
        self.addCleanup(deploy.select_target, "design")
        host = deploy.Host({}, Path("/tmp/unused-visit-credit-compatibility.log"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "deploy").mkdir()
            (target / "deploy/booking-completion-v1.capability").write_bytes(
                (ROOT / "deploy/booking-completion-v1.capability").read_bytes()
            )
            # The earlier visit-credit capability cannot read the newer
            # fee-eligible component format; it still requires the database probe.
            (target / "deploy/visit-credit-v1.capability").write_bytes(
                (ROOT / "deploy/visit-credit-v1.capability").read_bytes()
            )
            with (
                patch.object(host, "command", side_effect=["t", "t"]),
                self.assertRaisesRegex(deploy.DeployError, "visit credit"),
            ):
                host.ensure_compatible_release(target)
            for replies in (
                ["f", "f", "f", "f", "f", "f", "f", "f", "f"],
                ["t", "f", "f", "f", "f", "f", "f", "f", "f", "f"],
            ):
                with patch.object(host, "command", side_effect=[*replies, "f"]):
                    host.ensure_compatible_release(target)

    def test_older_release_cannot_manage_accepted_first_membership_splits(self):
        deploy.select_target("functional")
        self.addCleanup(deploy.select_target, "design")
        host = deploy.Host({}, Path("/tmp/unused-membership-split-compatibility.log"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "deploy").mkdir()
            for marker in ("booking-completion-v1.capability", "visit-credit-v2.capability"):
                (target / "deploy" / marker).write_bytes((ROOT / "deploy" / marker).read_bytes())
            with (
                patch.object(host, "command", side_effect=["t", "t"]),
                self.assertRaisesRegex(deploy.DeployError, "split membership"),
            ):
                host.ensure_compatible_release(target)
            for replies in (
                ["f", "f", "f", "f", "f", "f", "f", "f"],
                ["t", "f", "f", "f", "f", "f", "f", "f", "f"],
            ):
                with patch.object(host, "command", side_effect=[*replies, "f"]):
                    host.ensure_compatible_release(target)

    def test_older_release_refuses_membership_allocations_of_recorded_bank_money(self):
        deploy.select_target("functional")
        self.addCleanup(deploy.select_target, "design")
        host = deploy.Host({}, Path("/tmp/unused-member-bank-compatibility.log"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "deploy").mkdir()
            for marker in (
                "booking-completion-v1.capability",
                "visit-credit-v2.capability",
                "membership-first-split-v1.capability",
            ):
                (target / "deploy" / marker).write_bytes((ROOT / "deploy" / marker).read_bytes())
            with (
                patch.object(host, "command", side_effect=["t", "t"]),
                self.assertRaisesRegex(deploy.DeployError, "membership bank allocations"),
            ):
                host.ensure_compatible_release(target)
            for replies in (
                ["f", "f", "f", "f", "f", "f", "f"],
                ["t", "f", "f", "f", "f", "f", "f", "f"],
            ):
                with patch.object(host, "command", side_effect=[*replies, "f"]):
                    host.ensure_compatible_release(target)

    def test_older_release_refuses_accepted_split_first_card_arrivals(self):
        deploy.select_target("functional")
        self.addCleanup(deploy.select_target, "design")
        host = deploy.Host({}, Path("/tmp/unused-first-card-arrival-compatibility.log"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "deploy").mkdir()
            for marker in (
                "booking-completion-v1.capability",
                "visit-credit-v2.capability",
                "membership-first-split-v1.capability",
                "membership-booking-zelle-v1.capability",
            ):
                (target / "deploy" / marker).write_bytes((ROOT / "deploy" / marker).read_bytes())
            with (
                patch.object(host, "command", side_effect=["t", "t"]),
                self.assertRaisesRegex(deploy.DeployError, "split membership arrivals"),
            ):
                host.ensure_compatible_release(target)
            for replies in (["f", "f", "f", "f", "f", "f"], ["t", "f", "f", "f", "f", "f", "f"]):
                with patch.object(host, "command", side_effect=[*replies, "f"]):
                    host.ensure_compatible_release(target)

    def test_older_release_refuses_accepted_pending_visit_receipts(self):
        deploy.select_target("functional")
        self.addCleanup(deploy.select_target, "design")
        host = deploy.Host({}, Path("/tmp/unused-first-card-arrival-compatibility.log"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "deploy").mkdir()
            for marker in (
                "booking-completion-v1.capability",
                "visit-credit-v2.capability",
                "membership-first-split-v1.capability",
                "membership-booking-zelle-v1.capability",
                "split-membership-arrival-v1.capability",
            ):
                (target / "deploy" / marker).write_bytes((ROOT / "deploy" / marker).read_bytes())
            with (
                patch.object(host, "command", side_effect=["t", "t"]),
                self.assertRaisesRegex(deploy.DeployError, "pending visit receipts"),
            ):
                host.ensure_compatible_release(target)
            for replies in (["f", "f", "f", "f", "f"], ["t", "f", "f", "f", "f", "f"]):
                with patch.object(host, "command", side_effect=[*replies, "f"]):
                    host.ensure_compatible_release(target)

    def test_older_release_refuses_recorded_pending_visit_returns(self):
        deploy.select_target("functional")
        self.addCleanup(deploy.select_target, "design")
        host = deploy.Host({}, Path("/tmp/unused-first-card-arrival-compatibility.log"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "deploy").mkdir()
            for marker in (
                "booking-completion-v1.capability",
                "visit-credit-v2.capability",
                "membership-first-split-v1.capability",
                "membership-booking-zelle-v1.capability",
                "split-membership-arrival-v1.capability",
                "pending-visit-receipts-v1.capability",
            ):
                (target / "deploy" / marker).write_bytes((ROOT / "deploy" / marker).read_bytes())
            with (
                patch.object(host, "command", side_effect=["t", "t"]),
                self.assertRaisesRegex(deploy.DeployError, "pending visit returns"),
            ):
                host.ensure_compatible_release(target)
            for replies in (["f", "f", "f", "f"], ["t", "f", "f", "f", "f"]):
                with patch.object(host, "command", side_effect=[*replies, "f"]):
                    host.ensure_compatible_release(target)

    def test_older_release_refuses_recorded_stopped_arrivals(self):
        deploy.select_target("functional")
        self.addCleanup(deploy.select_target, "design")
        host = deploy.Host({}, Path("/tmp/unused-first-card-arrival-compatibility.log"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "deploy").mkdir()
            for marker in (
                "booking-completion-v1.capability",
                "visit-credit-v2.capability",
                "membership-first-split-v1.capability",
                "membership-booking-zelle-v1.capability",
                "split-membership-arrival-v1.capability",
                "pending-visit-receipts-v1.capability",
                "pending-visit-returns-v1.capability",
            ):
                (target / "deploy" / marker).write_bytes((ROOT / "deploy" / marker).read_bytes())
            with (
                patch.object(host, "command", side_effect=["t", "t"]),
                self.assertRaisesRegex(deploy.DeployError, "stopped arrivals"),
            ):
                host.ensure_compatible_release(target)
            for replies in (["f", "f", "f"], ["t", "f", "f", "f"]):
                with patch.object(host, "command", side_effect=[*replies, "f"]):
                    host.ensure_compatible_release(target)

    def test_older_release_refuses_cancellation_linked_stopped_arrivals(self):
        deploy.select_target("functional")
        self.addCleanup(deploy.select_target, "design")
        host = deploy.Host({}, Path("/tmp/unused-first-card-arrival-compatibility.log"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "deploy").mkdir()
            for marker in (
                "booking-completion-v1.capability",
                "visit-credit-v2.capability",
                "membership-first-split-v1.capability",
                "membership-booking-zelle-v1.capability",
                "split-membership-arrival-v1.capability",
                "pending-visit-receipts-v1.capability",
                "pending-visit-returns-v1.capability",
                "pending-arrival-stop-v1.capability",
            ):
                (target / "deploy" / marker).write_bytes((ROOT / "deploy" / marker).read_bytes())
            with (
                patch.object(host, "command", side_effect=["t", "t"]),
                self.assertRaisesRegex(deploy.DeployError, "cancellation-linked stopped arrivals"),
            ):
                host.ensure_compatible_release(target)
            for replies in (["f", "f"], ["t", "f", "f"]):
                with patch.object(host, "command", side_effect=[*replies, "f"]):
                    host.ensure_compatible_release(target)

    def test_older_release_cannot_manage_paid_visit_membership_purchases(self):
        deploy.select_target("functional")
        self.addCleanup(deploy.select_target, "design")
        host = deploy.Host({}, Path("/tmp/unused-paid-visit-purchase-compatibility.log"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            with (
                patch.object(host, "command", side_effect=["t", "t"]),
                self.assertRaisesRegex(deploy.DeployError, "paid-visit membership purchases"),
            ):
                host.ensure_paid_visit_purchase_compatible(target)
            for replies in (["f"], ["t", "f"]):
                with patch.object(host, "command", side_effect=[*replies, "f"]):
                    self.assertTrue(host.ensure_paid_visit_purchase_compatible(target))

    def test_older_release_refuses_received_split_paid_visit_purchases(self):
        deploy.select_target("functional")
        self.addCleanup(deploy.select_target, "design")
        host = deploy.Host({}, Path("/tmp/unused-paid-visit-split-compatibility.log"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "deploy").mkdir()
            marker = "paid-visit-purchase-v1.capability"
            (target / "deploy" / marker).write_bytes((ROOT / "deploy" / marker).read_bytes())
            with (
                patch.object(host, "command", side_effect=["t", "t"]),
                self.assertRaisesRegex(deploy.DeployError, "received-split membership purchases"),
            ):
                host.ensure_paid_visit_purchase_compatible(target)
            for replies in (["f"], ["t", "f"]):
                with patch.object(host, "command", side_effect=[*replies, "f"]):
                    self.assertTrue(host.ensure_paid_visit_received_split_compatible(target))
            marker = "paid-visit-received-split-v1.capability"
            (target / "deploy" / marker).write_bytes((ROOT / "deploy" / marker).read_bytes())
            with patch.object(host, "command") as command:
                self.assertTrue(host.ensure_paid_visit_purchase_compatible(target))
            command.assert_not_called()

    def test_older_release_cannot_manage_conditional_paid_visit_card_reservations(self):
        deploy.select_target("functional")
        self.addCleanup(deploy.select_target, "design")
        host = deploy.Host({}, Path("/tmp/unused-paid-visit-card-compatibility.log"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            with (
                patch.object(host, "command", side_effect=["t", "t"]),
                self.assertRaisesRegex(deploy.DeployError, "paid-visit card reservations"),
            ):
                host.ensure_paid_visit_card_compatible(target)
            for replies in (["f"], ["t", "f"]):
                with patch.object(host, "command", side_effect=replies):
                    self.assertTrue(host.ensure_paid_visit_card_compatible(target))
            (target / "deploy").mkdir()
            marker = "paid-visit-card-v1.capability"
            (target / "deploy" / marker).write_bytes((ROOT / "deploy" / marker).read_bytes())
            with patch.object(host, "command") as command:
                self.assertTrue(host.ensure_paid_visit_card_compatible(target))
            command.assert_not_called()


class BookingUpgradeTests(TransactionTestCase):
    def test_actual_additive_upgrade_preserves_legacy_booking_and_grant_failure_rolls_back(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL migration/privilege check")
        role = "mdo_book_" + uuid.uuid4().hex[:10]
        backup = "mdo_back_" + uuid.uuid4().hex[:10]
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE "{role}" NOLOGIN')
            cursor.execute(f'CREATE ROLE "{backup}" NOLOGIN')
        try:
            executor = MigrationExecutor(connection)
            executor.migrate([schema.BASELINE])
            historical = executor.loader.project_state([schema.BASELINE]).apps
            customer = historical.get_model("core", "Customer").objects.create(
                last_name="Fictional preserved family",
                phone="2025550176",
                email="preserved-stage@example.invalid",
            )
            start = timezone.now() + timedelta(days=1)
            session = historical.get_model("core", "Session").objects.create(
                starts_at=start, ends_at=start + timedelta(minutes=75)
            )
            booking = historical.get_model("core", "Booking").objects.create(
                customer=customer, session=session, children=2, adults=1
            )
            fields = [field.attname for field in booking._meta.concrete_fields]
            before = {field: getattr(booking, field) for field in fields}
            with (
                patch.object(schema, "guard_database"),
                patch.object(schema, "RUNTIME_ROLE", role),
                patch.object(schema, "BACKUP_ROLE", backup),
            ):
                output = io.StringIO()
                call_command("reviewed_booking_completion_schema", stdout=output)
                self.assertEqual(
                    json.loads(output.getvalue())["pending"], list(schema.REVIEWED_NAMES)
                )
                with (
                    patch.object(
                        schema, "grant_runtime_access", side_effect=CommandError("test grant fault")
                    ),
                    self.assertRaisesRegex(CommandError, "test grant fault"),
                ):
                    call_command(
                        "reviewed_booking_completion_schema", apply=True, stdout=io.StringIO()
                    )
                with connection.cursor() as cursor:
                    cursor.execute("SELECT to_regclass('public.core_paymentoperation') IS NULL")
                    self.assertTrue(cursor.fetchone()[0])
                call_command("reviewed_booking_completion_schema", apply=True, stdout=io.StringIO())
                from core.models import Booking

                after = Booking.objects.get(pk=booking.pk)
                self.assertEqual({field: getattr(after, field) for field in fields}, before)
                self.assertEqual(after.workflow, "legacy_test")
                # The previous release is restarted after additive schema preparation.
                # Its historical ORM omits both newly added NOT NULL columns.
                legacy_insert = historical.get_model("core", "Booking").objects.create(
                    customer=customer, session=session, children=1, adults=1
                )
                compatible = Booking.objects.get(pk=legacy_insert.pk)
                self.assertEqual(compatible.workflow, "legacy_test")
                self.assertEqual(compatible.zelle_sender, "")
                call_command("reviewed_booking_completion_schema", apply=True, stdout=io.StringIO())
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT has_table_privilege(%s,'core_financialposting','SELECT,INSERT'), has_table_privilege(%s,'core_financialposting','UPDATE'), has_table_privilege(%s,'core_paymentoperation','UPDATE'), has_table_privilege(%s,'core_paymentoperation','DELETE'), has_table_privilege(%s,'core_customer','SELECT'), has_table_privilege(%s,'core_customer','UPDATE'), has_table_privilege(%s,'core_backuprun','INSERT,UPDATE')",
                        [role, role, role, role, backup, backup, backup],
                    )
                    self.assertEqual(
                        cursor.fetchone(), (True, False, True, False, True, False, True)
                    )
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
            with connection.cursor() as cursor:
                for name in [role, backup]:
                    cursor.execute(f'DROP OWNED BY "{name}"')
                    cursor.execute(f'DROP ROLE "{name}"')

    def test_identity_guard_rejects_test_database(self):
        with self.assertRaises(CommandError):
            call_command("reviewed_booking_completion_schema", stdout=io.StringIO())
