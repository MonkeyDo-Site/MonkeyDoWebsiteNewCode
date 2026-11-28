"""Real PostgreSQL recovery, dispatch and release serialization."""

import uuid

from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.membership_paid_visit_pending import stop, stop_facts
from core.membership_paid_visit_records import (
    MembershipPaidVisitRecovery,
    MembershipPaidVisitRelease,
)
from core.models import PaymentOperation
from core.payments.operations import begin_dispatch
from tests import test_customer_credit_concurrency as races
from tests import test_membership_paid_visit_recovery as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitRecoveryRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = races.CustomerCreditRaceTests.setUp
    race = races.CustomerCreditRaceTests.race
    prepare = fixtures.PaidVisitRecoveryTests.prepare
    buy_card = fixtures.PaidVisitRecoveryTests.buy_card
    decline = fixtures.PaidVisitRecoveryTests.decline
    setup_decline = fixtures.PaidVisitRecoveryTests.setup_decline
    request = fixtures.PaidVisitRecoveryTests.request

    def test_duplicate_confirmation_has_one_authority_and_one_remainder(self):
        self.setup_decline()
        results = self.race(self.request, self.request)
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipPaidVisitRecovery.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_distinct_reviews_of_same_decline_cannot_both_request_money(self):
        self.setup_decline()
        results = self.race(self.request, lambda: self.request(request_key=uuid.uuid4()))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(MembershipPaidVisitRecovery.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_owner_stop_and_recovery_cannot_both_release_and_collect(self):
        self.setup_decline()
        data = stop_facts(self.intent)

        def release():
            return stop(
                actor=self.owner,
                intent_id=self.intent.pk,
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                reason="Keep visit",
            )

        results = self.race(self.request, release)
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertNotEqual(
            MembershipPaidVisitRecovery.objects.exists(),
            MembershipPaidVisitRelease.objects.exists(),
        )

    def test_owner_stop_and_dispatch_cannot_leave_a_sending_released_request(self):
        self.setup_decline()
        authority = self.request()
        data = stop_facts(self.intent)

        def release():
            return stop(
                actor=self.owner,
                intent_id=self.intent.pk,
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                reason="Keep visit",
            )

        self.race(lambda: begin_dispatch(authority.operation.pk), release)
        authority.operation.refresh_from_db()
        if MembershipPaidVisitRelease.objects.exists():
            self.assertEqual(authority.operation.state, "cancelled")
        else:
            self.assertEqual(authority.operation.state, "sending")

    def test_used_recovery_refuses_schema_reversal(self):
        self.setup_decline()
        self.request()
        with self.assertRaisesMessage(RuntimeError, "card recoveries exist"), transaction.atomic():
            MigrationExecutor(connection).migrate([("core", "0086_paid_visit_card_reservations")])
        self.assertEqual(MembershipPaidVisitRecovery.objects.count(), 1)

    def test_unused_recovery_reverses_and_restores_before_runtime_request(self):
        try:
            MigrationExecutor(connection).migrate([("core", "0086_paid_visit_card_reservations")])
        finally:
            MigrationExecutor(connection).migrate([("core", "0091_combined_membership_renewals")])
        self.setup_decline()
        with self.runtime_role():
            self.request()
        self.assertEqual(MembershipPaidVisitRecovery.objects.count(), 1)
