"""Real PostgreSQL transactions keep conditional source reservations exclusive."""

import uuid

from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.customer_credit_records import VisitMembershipConversion
from core.membership_paid_visit_pending import complete
from core.membership_paid_visit_records import MembershipPaidVisitIntent, MembershipPaidVisitRelease
from core.membership_sales import offer, purchase
from core.models import PaymentOperation
from core.payments.ledger import request_operation
from tests import test_customer_credit_concurrency as setup_fixtures
from tests import test_membership_paid_visit_card as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitCardRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = setup_fixtures.CustomerCreditRaceTests.setUp
    race = setup_fixtures.CustomerCreditRaceTests.race
    prepare = fixtures.PaidVisitCardTests.prepare
    buy_card = fixtures.PaidVisitCardTests.buy_card
    approve = fixtures.PaidVisitCardTests.approve

    def test_duplicate_initial_request_has_one_source_reservation_and_one_card_request(self):
        self.prepare(card=True, expected_method="card")
        data = offer(**self.options)
        key = uuid.uuid4()

        def start():
            return purchase(
                **self.options,
                request_key=key,
                reviewed=data["fingerprint"],
                accepted=True,
                method_id=self.method.pk,
            )

        results = self.race(start, start)
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipPaidVisitIntent.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_initial_card_reservation_and_original_refund_cannot_both_reserve_source(self):
        self.prepare(card=True, expected_method="card")
        data = offer(**self.options)
        original = self.original.operations.get()

        def start():
            return purchase(
                **self.options,
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                accepted=True,
                method_id=self.method.pk,
            )

        def refund():
            return request_operation(
                actor=self.owner,
                sale_id=self.original.pk,
                request_key=uuid.uuid4(),
                tender="card",
                kind="refund",
                purpose="correction",
                original_id=original.pk,
                method_id=original.method_id,
                allocation=original.allocation,
            )

        results = self.race(start, refund)
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertNotEqual(
            MembershipPaidVisitIntent.objects.exists(),
            PaymentOperation.objects.filter(kind="refund").exists(),
        )

    def test_duplicate_completion_consumes_source_and_benefit_once(self):
        self.buy_card()
        self.approve()
        results = self.race(lambda: complete(self.intent.pk), lambda: complete(self.intent.pk))
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)
        self.assertEqual(MembershipPaidVisitRelease.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertEqual(self.visit.membership_benefits.filter(current__status="used").count(), 1)

    def test_used_reservation_refuses_schema_reversal(self):
        self.buy_card()
        with (
            self.assertRaisesMessage(RuntimeError, "card reservations exist"),
            transaction.atomic(),
        ):
            MigrationExecutor(connection).migrate([("core", "0085_paid_visit_received_split")])
        self.assertEqual(MembershipPaidVisitIntent.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_unused_guard_reverses_then_restores_before_runtime_card_purchase(self):
        try:
            MigrationExecutor(connection).migrate([("core", "0085_paid_visit_received_split")])
        finally:
            MigrationExecutor(connection).migrate([("core", "0087_paid_visit_card_recovery")])
        with self.runtime_role():
            self.buy_card()
        self.assertEqual(MembershipPaidVisitIntent.objects.count(), 1)
