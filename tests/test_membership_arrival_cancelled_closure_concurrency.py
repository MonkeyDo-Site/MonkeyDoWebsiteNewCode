"""Cancellation-linked stop records survive retries, refunds and code recovery."""

import uuid
from decimal import Decimal

from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core import membership_arrival_closure as closure
from core.membership_cancellations import plan_paid, request_refund
from core.membership_records import MembershipArrivalClosure, MembershipRefundPlan
from core.models import PaymentOperation
from tests import test_customer_credit_concurrency as setup_fixtures
from tests import test_membership_arrival_cancelled_closure as fixtures
from tests import test_membership_arrival_closure as kept
from tests import test_membership_arrival_returns_concurrency as races
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class CancelledArrivalClosureRaceTests(
    InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase
):
    setUp = setup_fixtures.CustomerCreditRaceTests.setUp
    overlap = races.PendingVisitReturnRaceTests.overlap
    prepare = fixtures.CancelledMembershipClosureTests.prepare
    start = fixtures.CancelledMembershipClosureTests.start
    mixed = fixtures.CancelledMembershipClosureTests.mixed
    accept = fixtures.CancelledMembershipClosureTests.accept
    result = fixtures.CancelledMembershipClosureTests.result
    paid = fixtures.CancelledMembershipClosureTests.paid
    unresolved = fixtures.CancelledMembershipClosureTests.unresolved
    give_back = fixtures.CancelledMembershipClosureTests.give_back
    cancelled = fixtures.CancelledMembershipClosureTests.cancelled
    returned = fixtures.CancelledMembershipClosureTests.returned
    stop = fixtures.CancelledMembershipClosureTests.stop

    def stop_options(self):
        return dict(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed_hash=closure.review(actor=self.owner, intent=self.intent)[1],
            reason="Keep booking and recorded membership cancellation",
            confirmed=True,
        )

    def test_duplicate_cancelled_stop_keeps_one_fact_and_no_new_payment(self):
        self.returned()
        options = self.stop_options()
        a, b = self.overlap(lambda: closure.stop(**options).pk, lambda: closure.stop(**options).pk)
        self.assertEqual(a, b)
        self.assertEqual(a[0], "ok")
        self.assertEqual(MembershipArrivalClosure.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_distinct_requests_cannot_create_two_cancelled_closures(self):
        self.returned()
        options = self.stop_options()
        a, b = self.overlap(
            lambda: closure.stop(**options).pk,
            lambda: closure.stop(**(options | dict(request_key=uuid.uuid4()))).pk,
        )
        self.assertEqual(sorted([a[0], b[0]]), ["blocked", "ok"])
        self.assertEqual(MembershipArrivalClosure.objects.count(), 1)

    def test_actual_membership_refund_and_visit_stop_preserve_their_separate_facts(self):
        self.returned()
        options = self.stop_options()
        plan = self.cancellation.refund_plans.get(original__tender="cash")
        a, b = self.overlap(
            lambda: closure.stop(**options).pk,
            lambda: (
                request_refund(
                    actor=self.owner,
                    plan_id=plan.pk,
                    request_key=uuid.uuid4(),
                    confirmed=True,
                    manual_returned=True,
                    refund_amount="2",
                ).pk
            ),
        )
        self.assertEqual(b[0], "ok")
        if a[0] != "ok":
            self.stop()
        saved = MembershipArrivalClosure.objects.get()
        self.assertIn(saved.facts["cancellation"]["refund_due"], ("15.00", "13.00"))
        self.assertEqual(
            sum(
                (p.amount - plan_paid(p) for p in MembershipRefundPlan.objects.all()), Decimal("0")
            ),
            Decimal("13"),
        )
        self.assertEqual(PaymentOperation.objects.count(), 4)
        self.assertFalse(self.play.checkouts.exists())

    def test_used_cancelled_reference_blocks_schema_reversal_without_losing_history(self):
        self.returned()
        self.stop()
        with (
            self.assertRaisesMessage(RuntimeError, "Cancelled-membership arrival closures exist"),
            transaction.atomic(),
        ):
            MigrationExecutor(connection).migrate([("core", "0082_stop_pending_arrival")])
        self.assertEqual(MembershipArrivalClosure.objects.count(), 1)
        self.assertIn(
            ("core", "0083_cancelled_membership_arrival_stop"),
            MigrationExecutor(connection).loader.applied_migrations,
        )

    def test_unused_reference_reverses_and_restores_before_runtime_stop(self):
        try:
            MigrationExecutor(connection).migrate([("core", "0082_stop_pending_arrival")])
        finally:
            MigrationExecutor(connection).migrate([("core", "0095_unused_membership_owner_dates")])
        self.returned()
        with self.runtime_role():
            self.stop()
        self.assertEqual(MembershipArrivalClosure.objects.count(), 1)

    def test_existing_kept_member_closure_is_not_rewritten_by_upgrade_or_reversal(self):
        kept.ArrivalClosureTests.reconciled(self)
        record = self.stop()
        facts = record.facts
        self.assertIsNone(record.cancellation_id)
        try:
            MigrationExecutor(connection).migrate([("core", "0082_stop_pending_arrival")])
        finally:
            MigrationExecutor(connection).migrate([("core", "0095_unused_membership_owner_dates")])
        record.refresh_from_db()
        self.assertEqual(record.facts, facts)
        self.assertIsNone(record.cancellation_id)
        self.assertEqual(MembershipArrivalClosure.objects.count(), 1)
