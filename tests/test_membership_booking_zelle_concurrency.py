import uuid
from decimal import Decimal

from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from core.membership_records import MembershipBankAllocation
from core.payments.models import ZelleRefund
from core.payments.zelle import facts
from tests import test_customer_credit_concurrency as races
from tests import test_membership_booking_zelle as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures


@override_settings(**SETTINGS)
class MembershipBankRaceTests(InitialCreditFixtures, TransactionTestCase):
    setUp = races.CustomerCreditRaceTests.setUp
    race = races.CustomerCreditRaceTests.race
    start = fixtures.MembershipBookingZelleTests.start
    prepare = fixtures.MembershipBookingZelleTests.prepare
    commit = fixtures.MembershipBookingZelleTests.commit

    def test_concurrent_direct_refund_records_share_one_original_source_budget(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL source advisory-lock race")
        self.start()

        def refund():
            try:
                with transaction.atomic():
                    return ZelleRefund.objects.create(
                        receipt=self.bank,
                        request_key=uuid.uuid4(),
                        amount="25",
                        completed_on=timezone.localdate(),
                        actor=self.owner,
                    )
            except DatabaseError as error:
                self.assertIn("Recorded Zelle source balance exceeded", str(error))
                return None

        results = self.race(refund, refund)
        self.assertEqual(sum(item is not None for item in results), 1)
        self.assertEqual(ZelleRefund.objects.count(), 1)
        self.assertEqual(facts(self.play)["available"], 0)

    def test_reverse_refuses_accepted_allocations_before_removing_source_checks(self):
        self.start()
        self.commit()
        with (
            self.assertRaisesMessage(RuntimeError, "Accepted membership bank allocations"),
            transaction.atomic(),
        ):
            MigrationExecutor(connection).migrate([("core", "0076_membership_first_split")])
        self.assertEqual(MembershipBankAllocation.objects.get().amount, Decimal("20"))
        self.assertIn(
            ("core", "0077_membership_booking_zelle"),
            MigrationExecutor(connection).loader.applied_migrations,
        )
        self.assertEqual(facts(self.play)["available"], 0)

    def test_unused_stage_reverses_and_restores_then_accepts_original_bank_money(self):
        try:
            MigrationExecutor(connection).migrate([("core", "0076_membership_first_split")])
        finally:
            MigrationExecutor(connection).migrate([("core", "0091_combined_membership_renewals")])
        self.start()
        self.commit()
        self.assertEqual(MembershipBankAllocation.objects.get().amount, Decimal("20"))
