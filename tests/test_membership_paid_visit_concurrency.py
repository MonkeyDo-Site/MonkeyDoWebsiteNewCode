"""Real PostgreSQL overlap cannot convert a paid visit or its funds twice."""

import uuid

from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.customer_credit_records import VisitMembershipConversion
from core.membership_sales import offer, purchase
from core.models import MembershipDraft, PaymentOperation
from core.payments.ledger import request_operation
from tests import test_customer_credit_concurrency as setup_fixtures
from tests import test_membership_paid_visit as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitPurchaseRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = setup_fixtures.CustomerCreditRaceTests.setUp
    race = setup_fixtures.CustomerCreditRaceTests.race
    prepare = fixtures.PaidVisitPurchaseTests.prepare
    commit = fixtures.PaidVisitPurchaseTests.commit

    def confirmation(self, key):
        current = offer(**self.options)
        return lambda: purchase(
            **self.options,
            request_key=key,
            reviewed=current["fingerprint"],
            accepted=True,
            verified_received=True,
            method_id=self.method.pk,
        )

    def test_duplicate_request_has_one_purchase_conversion_and_new_receipt(self):
        self.prepare()
        confirm = self.confirmation(uuid.uuid4())
        results = self.race(confirm, confirm)
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipDraft.objects.count(), 1)
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_two_distinct_requests_cannot_both_convert_the_same_visit(self):
        self.prepare()
        results = self.race(self.confirmation(uuid.uuid4()), self.confirmation(uuid.uuid4()))
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(MembershipDraft.objects.count(), 1)
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_original_refund_and_first_purchase_cannot_reserve_the_same_funds(self):
        self.prepare()
        original = self.original.operations.get()

        def refund():
            return request_operation(
                actor=self.owner,
                sale_id=self.original.pk,
                request_key=uuid.uuid4(),
                tender="cash",
                kind="refund",
                original_id=original.pk,
                allocation=original.allocation,
                purpose="correction",
            )

        results = self.race(self.confirmation(uuid.uuid4()), refund)
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertNotEqual(
            VisitMembershipConversion.objects.exists(),
            PaymentOperation.objects.filter(kind="refund").exists(),
        )

    def test_used_purchase_refuses_schema_reversal_without_losing_original_facts(self):
        self.prepare()
        member = self.commit()
        original = VisitMembershipConversion.objects.get(purchase=member).details
        with (
            self.assertRaisesMessage(RuntimeError, "Paid-visit membership purchases exist"),
            transaction.atomic(),
        ):
            MigrationExecutor(connection).migrate(
                [("core", "0083_cancelled_membership_arrival_stop")]
            )
        self.assertEqual(VisitMembershipConversion.objects.get(purchase=member).details, original)
        self.assertIn(
            ("core", "0084_paid_visit_purchase"),
            MigrationExecutor(connection).loader.applied_migrations,
        )

    def test_unused_guard_reverses_and_restores_before_runtime_purchase(self):
        try:
            MigrationExecutor(connection).migrate(
                [("core", "0083_cancelled_membership_arrival_stop")]
            )
        finally:
            MigrationExecutor(connection).migrate([("core", "0086_paid_visit_card_reservations")])
        self.prepare()
        with self.runtime_role():
            self.commit()
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)
