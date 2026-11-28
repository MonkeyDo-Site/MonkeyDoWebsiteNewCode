"""Actual transactions serialize source cancellation, release and subsequent use."""

import uuid

from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.membership_paid_visit_cancellation import release, review
from core.membership_paid_visit_pending import active, locked
from core.membership_paid_visit_records import MembershipPaidVisitCancellation
from core.membership_sales import offer, purchase
from core.models import FinancialLineAdjustment
from core.payments.invoices import total
from core.payments.ledger import request_operation
from tests import test_customer_credit_concurrency as races
from tests import test_membership_paid_visit_cancellation as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitCancellationRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = races.CustomerCreditRaceTests.setUp
    race = races.CustomerCreditRaceTests.race
    prepare = fixtures.PaidVisitCancellationTests.prepare
    buy_card = fixtures.PaidVisitCancellationTests.buy_card
    funded = fixtures.PaidVisitCancellationTests.funded
    cancelled = fixtures.PaidVisitCancellationTests.cancelled
    return_funds = fixtures.PaidVisitCancellationTests.return_funds
    finish = fixtures.PaidVisitCancellationTests.finish

    def prepare_release(self):
        self.cancelled()
        self.return_funds()
        with transaction.atomic():
            data = review(actor=self.owner, intent=locked(self.intent.pk))
        self.release_options = dict(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed=data["fingerprint"],
            reason="Keep original visit",
            confirmed=True,
        )

    def test_duplicate_release_records_one_decision_and_one_uncollected_adjustment(self):
        self.prepare_release()
        results = self.race(
            lambda: release(**self.release_options), lambda: release(**self.release_options)
        )
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipPaidVisitCancellation.objects.count(), 1)
        self.assertEqual(
            FinancialLineAdjustment.objects.filter(reason="membership_uncollected").count(), 1
        )

    def test_distinct_keys_cannot_both_cancel_the_same_uncollected_amount(self):
        self.prepare_release()
        results = self.race(
            lambda: release(**self.release_options),
            lambda: release(**(self.release_options | dict(request_key=uuid.uuid4()))),
        )
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(MembershipPaidVisitCancellation.objects.count(), 1)

    def test_another_purchase_can_reserve_source_only_after_release_commits(self):
        self.prepare_release()

        def other_purchase():
            data = offer(**self.options)
            return purchase(
                **self.options,
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                accepted=True,
                method_id=self.method.pk,
            )

        results = self.race(lambda: release(**self.release_options), other_purchase)
        self.assertIsNotNone(results[0])
        self.assertLessEqual(active().filter(booking=self.visit).count(), 1)
        self.assertEqual(
            total(self.member.installments.first().invoice.sale),
            self.operation.amount - self.cancellation.refund_amount,
        )
        self.assertEqual(MembershipPaidVisitCancellation.objects.count(), 1)

    def test_separate_original_refund_is_available_only_after_release(self):
        self.prepare_release()
        original = self.original.operations.get()

        def separate_refund():
            return request_operation(
                actor=self.owner,
                sale_id=self.original.pk,
                request_key=uuid.uuid4(),
                tender="card",
                kind="refund",
                purpose="correction",
                original_id=original.pk,
                method_id=original.method_id,
                allocation=[
                    original.allocation[0]
                    | dict(net="1.00", fee="0.00", item_tax="0.00", fee_tax="0.00")
                ],
            )

        results = self.race(lambda: release(**self.release_options), separate_refund)
        self.assertIsNotNone(results[0])
        self.assertEqual(MembershipPaidVisitCancellation.objects.count(), 1)
        self.assertFalse(
            self.original.operations.exclude(kind="receipt").filter(state="succeeded").exists()
        )

    def test_used_cancelled_release_refuses_older_schema(self):
        self.prepare_release()
        release(**self.release_options)
        with (
            self.assertRaisesMessage(RuntimeError, "Cancelled paid visit releases exist"),
            transaction.atomic(),
        ):
            MigrationExecutor(connection).migrate([("core", "0087_paid_visit_card_recovery")])
        self.assertEqual(MembershipPaidVisitCancellation.objects.count(), 1)

    def test_unused_migration_restores_before_runtime_release(self):
        try:
            MigrationExecutor(connection).migrate([("core", "0087_paid_visit_card_recovery")])
        finally:
            MigrationExecutor(connection).migrate([("core", "0095_unused_membership_owner_dates")])
        self.prepare_release()
        with self.runtime_role():
            release(**self.release_options)
        self.assertEqual(MembershipPaidVisitCancellation.objects.count(), 1)
