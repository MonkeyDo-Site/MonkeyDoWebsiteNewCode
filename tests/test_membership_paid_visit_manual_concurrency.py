"""Actual PostgreSQL alternatives serialize with card requests and source release."""

import uuid
from unittest.mock import patch

from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.membership_paid_visit_pending import stop, stop_facts
from core.membership_paid_visit_records import (
    MembershipPaidVisitManualPayment,
    MembershipPaidVisitRecovery,
    MembershipPaidVisitRelease,
)
from core.membership_paid_visit_recovery import request as recover
from core.membership_paid_visit_recovery import review as card_review
from core.models import PaymentOperation
from tests import test_customer_credit_concurrency as races
from tests import test_membership_paid_visit_manual as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitManualRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = races.CustomerCreditRaceTests.setUp
    race = races.CustomerCreditRaceTests.race
    prepare = fixtures.PaidVisitManualTests.prepare
    buy_card = fixtures.PaidVisitManualTests.buy_card
    decline = fixtures.PaidVisitManualTests.decline
    setup_decline = fixtures.PaidVisitManualTests.setup_decline
    prepare_manual = fixtures.PaidVisitManualTests.prepare_manual
    receive = fixtures.PaidVisitManualTests.receive

    def test_duplicate_confirmations_record_one_actual_receipt(self):
        self.prepare_manual()
        results = self.race(self.receive, self.receive)
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipPaidVisitManualPayment.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_distinct_keys_cannot_record_the_same_remainder_twice(self):
        self.prepare_manual()
        results = self.race(self.receive, lambda: self.receive(request_key=uuid.uuid4()))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(MembershipPaidVisitManualPayment.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_card_request_and_manual_receipt_cannot_both_claim_remaining_money(self):
        self.prepare_manual()
        data = card_review(actor=self.staff, intent_id=self.intent.pk, method_id=self.method.pk)

        def card():
            return recover(
                actor=self.staff,
                intent_id=self.intent.pk,
                method_id=self.method.pk,
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                confirmed=True,
            )

        results = self.race(self.receive, card)
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(
            MembershipPaidVisitManualPayment.objects.count()
            + MembershipPaidVisitRecovery.objects.count(),
            1,
        )
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_source_release_and_receipt_cannot_both_commit(self):
        self.prepare_manual()
        data = stop_facts(self.intent)

        def release():
            return stop(
                actor=self.owner,
                intent_id=self.intent.pk,
                request_key=uuid.uuid4(),
                reviewed=data["fingerprint"],
                reason="Keep original visit",
            )

        results = self.race(self.receive, release)
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(
            MembershipPaidVisitManualPayment.objects.count()
            + MembershipPaidVisitRelease.objects.count(),
            1,
        )

    def test_used_manual_schema_refuses_reversal_to_published_0089(self):
        self.prepare_manual()
        self.receive()
        with self.assertRaisesRegex(RuntimeError, "have been used"), transaction.atomic():
            MigrationExecutor(connection).migrate(
                [("core", "0089_paid_visit_recovery_card_storage")]
            )
        self.assertEqual(MembershipPaidVisitManualPayment.objects.count(), 1)

    def test_unused_schema_restores_exact_old_guards_and_runtime_receipt(self):
        functions = (
            "monkeydo_paid_visit_member_lock",
            "monkeydo_paid_visit_card_complete",
            "monkeydo_paid_visit_cancelled_scope",
        )

        def definitions():
            with connection.cursor() as cursor:
                return [
                    cursor.execute("SELECT pg_get_functiondef(%s::regproc)", [name]).fetchone()[0]
                    for name in functions
                ]

        MigrationExecutor(connection).migrate([("core", "0089_paid_visit_recovery_card_storage")])
        before = definitions()
        self.assertNotIn(
            "core_membershippaidvisitmanualpayment", connection.introspection.table_names()
        )
        MigrationExecutor(connection).migrate([("core", "0092_combined_renewal_bank_receipt")])
        MigrationExecutor(connection).migrate([("core", "0089_paid_visit_recovery_card_storage")])
        self.assertEqual(definitions(), before)
        MigrationExecutor(connection).migrate([("core", "0092_combined_renewal_bank_receipt")])
        self.prepare_manual()
        with self.runtime_role():
            self.receive()
        self.assertEqual(MembershipPaidVisitManualPayment.objects.count(), 1)

    def test_uncertain_new_card_storage_and_manual_receipt_cannot_both_start(self):
        from core.membership_paid_visit_manual import review
        from core.membership_paid_visit_new_card import pending
        from core.membership_paid_visit_records import MembershipPaidVisitCardStorage
        from core.payments.gateway import ProviderFailure
        from tests import test_membership_paid_visit_new_card as storage

        storage.PaidVisitNewCardTests.storage_flow(self)
        self.manual_key = uuid.uuid4()
        self.manual_data = review(actor=self.staff, intent_id=self.intent.pk)
        with patch("core.payments.setup.Gateway") as gateway:
            storage.PaidVisitNewCardTests.recovery_gateway(self, gateway)
            gateway.return_value.save_card.side_effect = ProviderFailure("synthetic_unknown")
            self.race(lambda: storage.PaidVisitNewCardTests.save_recovery_card(self), self.receive)
        self.assertEqual(
            MembershipPaidVisitCardStorage.objects.count()
            + MembershipPaidVisitManualPayment.objects.count(),
            1,
        )
        self.assertFalse(pending(self.intent) and MembershipPaidVisitManualPayment.objects.exists())
