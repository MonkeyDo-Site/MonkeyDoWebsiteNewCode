from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.membership_records import MembershipArrivalReceipt
from tests import test_customer_credit_concurrency as races
from tests import test_membership_arrival_first_card_split as fixtures
from tests import test_membership_arrival_first_card_split_concurrency as overlaps
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PendingVisitReceiptRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = races.CustomerCreditRaceTests.setUp
    prepare = fixtures.FirstSplitCardArrivalTests.prepare
    accept = fixtures.FirstSplitCardArrivalTests.accept

    def start(self):
        fixtures.FirstSplitCardArrivalTests.start(self)
        self.input["split"] = dict(cash="2", check="1")

    def test_overlapping_confirmation_records_each_received_tender_once(self):
        overlaps.SplitFirstCardRaceTests.test_overlapping_confirmation_preserves_one_manual_set_and_one_first_card_request(
            self
        )
        self.assertEqual(MembershipArrivalReceipt.objects.count(), 2)

    def test_used_receipt_scope_cannot_reverse(self):
        self.start()
        self.accept()
        with (
            self.assertRaisesMessage(RuntimeError, "Accepted pending visit receipts"),
            transaction.atomic(),
        ):
            MigrationExecutor(connection).migrate([("core", "0078_split_membership_arrival")])
        self.assertEqual(MembershipArrivalReceipt.objects.count(), 2)
        self.assertIn(
            ("core", "0079_pending_visit_receipts"),
            MigrationExecutor(connection).loader.applied_migrations,
        )

    def test_unused_scope_reverses_restores_and_accepts_received_money(self):
        try:
            MigrationExecutor(connection).migrate([("core", "0078_split_membership_arrival")])
        finally:
            MigrationExecutor(connection).migrate([("core", "0090_paid_visit_manual_payment")])
        self.start()
        self.accept()
        self.assertEqual(MembershipArrivalReceipt.objects.count(), 2)
