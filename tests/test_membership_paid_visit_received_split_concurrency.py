"""Verified split conversions retain source locks and refuse incompatible schema reversal."""

import uuid

from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.customer_credit_records import VisitMembershipConversion
from core.membership_sales import offer, purchase
from core.models import PaymentOperation
from tests import test_membership_paid_visit_concurrency as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitReceivedSplitRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = fixtures.PaidVisitPurchaseRaceTests.setUp
    race = fixtures.PaidVisitPurchaseRaceTests.race
    prepare = fixtures.PaidVisitPurchaseRaceTests.prepare
    confirmation = fixtures.PaidVisitPurchaseRaceTests.confirmation

    def prepare_split(self):
        self.prepare(expected_method="split", split={"cash": "1.00", "check": "1.00"})

    def test_duplicate_split_request_records_each_receipt_only_once(self):
        self.prepare_split()
        confirm = self.confirmation(uuid.uuid4())
        results = self.race(confirm, confirm)
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_distinct_split_requests_cannot_convert_the_same_source_twice(self):
        self.prepare_split()
        results = self.race(self.confirmation(uuid.uuid4()), self.confirmation(uuid.uuid4()))
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_used_split_guard_refuses_older_schema_and_keeps_all_original_receipts(self):
        self.prepare_split()
        data = offer(**self.options)
        purchase(
            **self.options,
            request_key=uuid.uuid4(),
            reviewed=data["fingerprint"],
            accepted=True,
            verified_received=True,
            method_id=self.method.pk,
        )
        with (
            self.assertRaisesMessage(RuntimeError, "Paid-visit split purchases exist"),
            transaction.atomic(),
        ):
            MigrationExecutor(connection).migrate([("core", "0084_paid_visit_purchase")])
        self.assertIn(
            ("core", "0085_paid_visit_received_split"),
            MigrationExecutor(connection).loader.applied_migrations,
        )
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_unused_split_guard_reverses_and_restores_before_runtime_confirmation(self):
        try:
            MigrationExecutor(connection).migrate([("core", "0084_paid_visit_purchase")])
        finally:
            MigrationExecutor(connection).migrate([("core", "0085_paid_visit_received_split")])
        self.prepare_split()
        data = offer(**self.options)
        with self.runtime_role():
            purchase(
                **self.options,
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                accepted=True,
                verified_received=True,
                method_id=self.method.pk,
            )
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)
