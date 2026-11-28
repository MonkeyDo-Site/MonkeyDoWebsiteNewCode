import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from core import membership_arrival_recovery as recovery
from core.membership_arrival_receipts import summary
from core.membership_arrival_returns import record, review
from core.membership_records import (
    MembershipArrivalReceiptApplication,
    MembershipArrivalReceiptReturn,
)
from tests import test_customer_credit_concurrency as races
from tests import test_membership_arrival_returns as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PendingVisitReturnRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = races.CustomerCreditRaceTests.setUp
    prepare = fixtures.PendingReturnTests.prepare
    start = fixtures.PendingReturnTests.start
    mixed = fixtures.PendingReturnTests.mixed
    accept = fixtures.PendingReturnTests.accept
    result = fixtures.PendingReturnTests.result
    paid = fixtures.PendingReturnTests.paid
    give_back = fixtures.PendingReturnTests.give_back

    def overlap(self, first, second):
        ready = Barrier(2)

        def run(action):
            close_old_connections()
            try:
                ready.wait(timeout=10)
                try:
                    return "ok", action()
                except (ValidationError, DatabaseError) as error:
                    return "blocked", str(error)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = pool.submit(run, first), pool.submit(run, second)
            return a.result(timeout=25), b.result(timeout=25)

    def return_options(self):
        return dict(
            actor=self.owner,
            receipt_id=self.cash.pk,
            request_key=uuid.uuid4(),
            value="2",
            completed_on=timezone.localdate(),
            reviewed_hash=review(actor=self.owner, receipt_id=self.cash.pk)["fingerprint"],
            confirmed=True,
            verified_returned=True,
        )

    def test_duplicate_return_confirmation_has_one_money_out_fact(self):
        self.paid()
        options = self.return_options()
        a, b = self.overlap(lambda: record(**options).pk, lambda: record(**options).pk)
        self.assertEqual(a, b)
        self.assertEqual(a[0], "ok")
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 1)
        self.assertEqual(summary(self.intent)["total"], Decimal("5"))

    def test_distinct_returns_cannot_both_spend_the_same_reviewed_source_balance(self):
        self.paid()
        options = self.return_options()
        a, b = self.overlap(
            lambda: record(**options).pk,
            lambda: record(**(options | dict(request_key=uuid.uuid4()))).pk,
        )
        self.assertEqual(sorted([a[0], b[0]]), ["blocked", "ok"])
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 1)
        self.assertEqual(summary(self.intent)["total"], Decimal("5"))

    def test_database_budget_serializes_distinct_raw_return_inserts(self):
        self.paid()

        def insert():
            with transaction.atomic():
                return MembershipArrivalReceiptReturn.objects.create(
                    receipt_id=self.cash.pk,
                    actor_id=self.owner.pk,
                    request_key=uuid.uuid4(),
                    fingerprint="f" * 64,
                    amount=Decimal("2"),
                    reviewed_available=Decimal("3"),
                    completed_on=timezone.localdate(),
                ).pk

        a, b = self.overlap(insert, insert)
        self.assertEqual(sorted([a[0], b[0]]), ["blocked", "ok"])
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 1)
        self.assertEqual(summary(self.intent)["total"], Decimal("5"))

    def test_return_and_arrival_application_cannot_both_spend_the_same_source(self):
        self.paid()
        options = self.return_options()
        data = self.input | dict(
            pending_review=self.intent.pk,
            pending_reason="Review remaining visit",
            method="card",
            split={},
        )
        quote = recovery.preview(actor=self.owner, intent=self.intent, data=data)[0]

        def finish():
            return recovery.confirm(
                actor=self.owner,
                intent_id=self.intent.pk,
                data=data,
                request_key=uuid.uuid4(),
                reviewed_hash=quote[-1],
                confirmed=True,
            ).pk

        a, b = self.overlap(lambda: record(**options).pk, finish)
        self.assertEqual(sorted([a[0], b[0]]), ["blocked", "ok"])
        self.assertEqual(bool(MembershipArrivalReceiptReturn.objects.exists()), a[0] == "ok")
        self.assertEqual(
            MembershipArrivalReceiptApplication.objects.count(), 4 if b[0] == "ok" else 0
        )
        self.cash.refresh_from_db()
        if hasattr(self.cash, "application"):
            self.assertEqual(self.cash.application.operation.amount, Decimal("3"))
        else:
            self.assertEqual(summary(self.intent)["total"], Decimal("5"))

    def test_used_return_scope_cannot_reverse(self):
        self.paid()
        self.give_back()
        with (
            self.assertRaisesMessage(RuntimeError, "Recorded pending visit returns"),
            transaction.atomic(),
        ):
            MigrationExecutor(connection).migrate([("core", "0079_pending_visit_receipts")])
        self.assertEqual(MembershipArrivalReceiptReturn.objects.count(), 1)
        self.assertIn(
            ("core", "0080_pending_visit_returns"),
            MigrationExecutor(connection).loader.applied_migrations,
        )

    def test_unused_return_scope_reverses_and_restores_before_recording(self):
        try:
            MigrationExecutor(connection).migrate([("core", "0079_pending_visit_receipts")])
        finally:
            MigrationExecutor(connection).migrate([("core", "0092_combined_renewal_bank_receipt")])
        self.paid()
        self.give_back()
        self.assertEqual(summary(self.intent)["total"], Decimal("5"))
