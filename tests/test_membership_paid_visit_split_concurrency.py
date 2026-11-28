"""Real commits retain known split receipts and serialize competing payment choices."""

import importlib
import uuid
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core.membership_paid_visit_split import card_review, confirm_split, request_card
from core.membership_paid_visit_split_records import (
    MembershipPaidVisitSplit,
    MembershipPaidVisitSplitCard,
)
from core.models import PaymentOperation
from core.payments.invoices import received
from tests import test_customer_credit_concurrency as setup
from tests import test_membership_cancellations as races
from tests import test_membership_paid_visit_split as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures


@override_settings(**SETTINGS)
class PaidVisitSplitRaceTests(InitialCreditFixtures, TransactionTestCase):
    setUp = setup.CustomerCreditRaceTests.setUp
    prepare = fixtures.PaidVisitSplitTests.prepare
    buy_card = fixtures.PaidVisitSplitTests.buy_card
    decline = fixtures.PaidVisitSplitTests.decline
    setup_decline = fixtures.PaidVisitSplitTests.setup_decline
    prepare_split = fixtures.PaidVisitSplitTests.prepare_split
    receive = fixtures.PaidVisitSplitTests.receive
    confirm = fixtures.PaidVisitSplitTests.confirm
    race = races.MembershipCancellationRaceTests.race

    def action(self, key):
        return confirm_split(
            **self.split_values,
            request_key=key,
            reviewed=self.split_quote["fingerprint"],
            verified_received=True,
            card_authorized=True,
        )[0]

    def test_same_request_commits_one_receipt_and_one_card_request(self):
        self.prepare_split()
        results = self.race(
            lambda: self.action(self.split_key), lambda: self.action(self.split_key)
        )
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(MembershipPaidVisitSplit.objects.count(), 1)
        self.assertEqual(MembershipPaidVisitSplitCard.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 4)

    def test_distinct_requests_cannot_both_record_the_same_intent(self):
        self.prepare_split()
        results = self.race(lambda: self.action(self.split_key), lambda: self.action(uuid.uuid4()))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(MembershipPaidVisitSplit.objects.count(), 1)
        self.assertEqual(MembershipPaidVisitSplitCard.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 4)

    def test_old_full_card_request_and_new_split_cannot_both_collect(self):
        from core.membership_paid_visit_records import MembershipPaidVisitRecovery
        from core.membership_paid_visit_recovery import request as old_request

        self.prepare_split()

        def original():
            return old_request(
                actor=self.staff,
                intent_id=self.intent.pk,
                method_id=self.method.pk,
                request_key=uuid.uuid4(),
                reviewed=self.data["fingerprint"],
                confirmed=True,
            )

        results = self.race(lambda: self.action(self.split_key), original)
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(
            MembershipPaidVisitSplit.objects.count() + MembershipPaidVisitRecovery.objects.count(),
            1,
        )
        self.assertEqual(PaymentOperation.objects.filter(tender="card", state="ready").count(), 1)
        self.assertFalse(self.visit.membership_benefits.exists())

    def test_known_receipt_commits_even_if_later_card_job_preparation_fails(self):
        self.prepare_split()
        with patch(
            "core.payments.jobs.enqueue",
            side_effect=DatabaseError("Simulated local job write failure"),
        ):
            split, card, problem = self.confirm()
        self.assertIsNone(card)
        self.assertTrue(problem)
        self.assertEqual(MembershipPaidVisitSplit.objects.count(), 1)
        self.assertEqual(MembershipPaidVisitSplitCard.objects.count(), 0)
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertEqual(str(received(self.member.installments.first().invoice.sale)), "0.97")
        current = card_review(actor=self.staff, split_id=split.pk, method_id=self.method.pk)
        request_card(
            actor=self.staff,
            split_id=split.pk,
            method_id=self.method.pk,
            request_key=uuid.uuid4(),
            reviewed=current["fingerprint"],
            confirmed=True,
        )
        self.assertEqual(PaymentOperation.objects.count(), 4)

    def test_used_split_history_refuses_reversal(self):
        self.prepare_split()
        split = self.receive()
        with self.assertRaisesMessage(RuntimeError, "cannot be reversed"), transaction.atomic():
            MigrationExecutor(connection).migrate(
                [("core", "0093_membership_calendar_corrections")]
            )
        self.assertEqual(MembershipPaidVisitSplit.objects.get().pk, split.pk)
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_unused_reverse_restores_published_functions_exactly_and_reapplies(self):
        self.prepare_split()
        migration = importlib.import_module("core.migrations.0094_paid_visit_split_remainder")
        definitions = (
            migration.OLD.MEMBER_SCOPE,
            migration.OLD_FEE,
            migration.OLD.COMPLETE_SCOPE,
            migration.OLD.CANCELLED_SCOPE,
            migration.OLD_UNCOLLECTED,
            migration.OLD_CANCELLED_COMPLETE,
        )
        names = (
            "monkeydo_paid_visit_member_lock()",
            "monkeydo_paid_visit_manual_fee()",
            "monkeydo_paid_visit_card_complete()",
            "monkeydo_paid_visit_cancelled_scope()",
            "monkeydo_paid_visit_uncollected_scope()",
            "monkeydo_paid_visit_cancelled_complete()",
        )
        try:
            MigrationExecutor(connection).migrate(
                [("core", "0093_membership_calendar_corrections")]
            )
            with connection.cursor() as cursor:
                for name, sql in zip(names, definitions, strict=True):
                    cursor.execute("SELECT pg_get_functiondef(%s::regprocedure)", [name])
                    before = cursor.fetchone()[0]
                    cursor.execute(sql, params=None)
                    cursor.execute("SELECT pg_get_functiondef(%s::regprocedure)", [name])
                    self.assertEqual(cursor.fetchone()[0], before)
            with self.assertRaisesMessage(ValidationError, "upgrade"):
                self.receive()
        finally:
            MigrationExecutor(connection).migrate([("core", "0095_unused_membership_owner_dates")])
        self.confirm()
        self.assertEqual(MembershipPaidVisitSplit.objects.count(), 1)
