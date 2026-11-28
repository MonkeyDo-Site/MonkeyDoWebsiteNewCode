"""A stopped pending arrival cannot race into an actual visit or reverse history."""

import uuid

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core import membership_arrival_closure as closure
from core import membership_arrival_recovery as recovery
from core.membership_records import MembershipArrivalCheckout, MembershipArrivalClosure
from core.models import Booking, PaymentOperation
from tests import test_membership_arrival_closure as fixtures
from tests import test_membership_arrival_returns_concurrency as races
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PendingArrivalStopRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = races.PendingVisitReturnRaceTests.setUp
    overlap = races.PendingVisitReturnRaceTests.overlap
    prepare = fixtures.ArrivalClosureTests.prepare
    start = fixtures.ArrivalClosureTests.start
    mixed = fixtures.ArrivalClosureTests.mixed
    accept = fixtures.ArrivalClosureTests.accept
    result = fixtures.ArrivalClosureTests.result
    paid = fixtures.ArrivalClosureTests.paid
    give_back = fixtures.ArrivalClosureTests.give_back
    reconciled = fixtures.ArrivalClosureTests.reconciled
    stop = fixtures.ArrivalClosureTests.stop

    def stop_options(self):
        return dict(
            actor=self.owner,
            intent_id=self.intent.pk,
            request_key=uuid.uuid4(),
            reviewed_hash=closure.review(actor=self.owner, intent=self.intent)[1],
            reason="Keep booking for a later review",
            confirmed=True,
        )

    def test_duplicate_stop_commits_one_record_without_new_visit_money(self):
        self.reconciled()
        options = self.stop_options()
        a, b = self.overlap(lambda: closure.stop(**options).pk, lambda: closure.stop(**options).pk)
        self.assertEqual(a, b)
        self.assertEqual(a[0], "ok")
        self.assertEqual(MembershipArrivalClosure.objects.count(), 1)
        self.assertFalse(MembershipArrivalCheckout.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 3)

    def test_distinct_stop_requests_cannot_both_end_same_arrival(self):
        self.reconciled()
        options = self.stop_options()
        a, b = self.overlap(
            lambda: closure.stop(**options).pk,
            lambda: closure.stop(**(options | dict(request_key=uuid.uuid4()))).pk,
        )
        self.assertEqual(sorted([a[0], b[0]]), ["blocked", "ok"])
        self.assertEqual(MembershipArrivalClosure.objects.count(), 1)
        self.assertFalse(MembershipArrivalCheckout.objects.exists())

    def test_stop_and_arrival_confirmation_cannot_both_commit(self):
        self.reconciled()
        options = self.stop_options()
        data = self.input | dict(
            pending_review=self.intent.pk,
            pending_reason="Finish current visit",
            method="card",
            split={},
            zelle_verified=False,
            gift_card_verified=False,
        )
        quote = recovery.preview(actor=self.owner, intent=self.intent, data=data)[0]

        def finish():
            return recovery.confirm(
                actor=self.owner,
                intent_id=self.intent.pk,
                data=data,
                request_key=uuid.uuid4(),
                reviewed_hash=quote[-1],
                confirmed=True,
            ).pk

        a, b = self.overlap(lambda: closure.stop(**options).pk, finish)
        self.assertEqual(sorted([a[0], b[0]]), ["blocked", "ok"])
        self.assertEqual(MembershipArrivalClosure.objects.exists(), a[0] == "ok")
        self.assertEqual(MembershipArrivalCheckout.objects.exists(), b[0] == "ok")
        self.assertEqual(
            Booking.objects.get(pk=self.play.pk).attendance, "arrived" if b[0] == "ok" else ""
        )
        self.assertEqual(PaymentOperation.objects.count(), 4 if b[0] == "ok" else 3)

    def test_used_stop_cannot_reverse_and_does_not_change_original_records(self):
        self.reconciled()
        self.stop()
        with (
            self.assertRaisesMessage(RuntimeError, "Stopped arrival records exist"),
            transaction.atomic(),
        ):
            MigrationExecutor(connection).migrate([("core", "0081_gift_cancellation_scope")])
        self.assertEqual(MembershipArrivalClosure.objects.count(), 1)
        self.assertIn(
            ("core", "0082_stop_pending_arrival"),
            MigrationExecutor(connection).loader.applied_migrations,
        )

    def test_unused_stop_scope_reverses_and_restores_before_valid_runtime_confirmation(self):
        try:
            MigrationExecutor(connection).migrate([("core", "0081_gift_cancellation_scope")])
        finally:
            MigrationExecutor(connection).migrate(
                [("core", "0096_credit_funded_membership_renewals")]
            )
        self.reconciled()
        with self.runtime_role():
            self.stop()
        self.assertEqual(MembershipArrivalClosure.objects.count(), 1)
        self.assertFalse(MembershipArrivalCheckout.objects.exists())

    def test_previous_review_cannot_be_used_after_a_distinct_booking_edit(self):
        self.reconciled()
        options = self.stop_options()
        Booking.objects.filter(pk=self.play.pk).update(edit_version=self.play.edit_version + 1)
        with self.assertRaisesMessage(ValidationError, "booking or received funds changed"):
            closure.stop(**options)
        self.assertFalse(MembershipArrivalClosure.objects.exists())
