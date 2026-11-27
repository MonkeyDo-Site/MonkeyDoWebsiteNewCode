"""Fresh owner consent and original worker authority cannot both finish a visit."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.db import connection
from django.test import TransactionTestCase, override_settings

from core import membership_arrival_pending
from core import membership_arrival_recovery as recovery
from core.membership_records import MembershipArrivalResolution, MembershipPurchase
from core.models import PaymentOperation
from tests import test_membership_arrival_pending_concurrency as pending
from tests import test_membership_arrival_recovery as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class OwnerArrivalRecoveryRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = pending.PendingArrivalRaceTests.setUp
    prepare = fixtures.OwnerArrivalRecoveryTests.prepare
    begin = fixtures.OwnerArrivalRecoveryTests.begin
    pay_first = fixtures.OwnerArrivalRecoveryTests.pay_first
    start = fixtures.OwnerArrivalRecoveryTests.start
    owner_review = fixtures.OwnerArrivalRecoveryTests.owner_review
    run_in_connection = pending.PendingArrivalRaceTests.run_in_connection

    def inputs(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL fresh-arrival authority races")
        self.start()
        self.reviewed = self.owner_review()

    def accept(self, key):
        return recovery.confirm(
            actor=self.owner,
            intent_id=self.intent.pk,
            data=self.recovery_data,
            request_key=key,
            reviewed_hash=self.reviewed[-1],
            confirmed=True,
        )

    def test_competing_new_owner_requests_cannot_create_two_visit_payments(self):
        self.inputs()
        created, competing = Event(), Event()
        original_confirm, original_locked = recovery.checkout.confirm, recovery.locked

        def paused_confirm(**kwargs):
            result = original_confirm(**kwargs)
            created.set()
            if not competing.wait(timeout=10):
                raise AssertionError("Competing owner never reached the arrival lock.")
            return result

        def checked_locked(intent_id):
            if created.is_set():
                competing.set()
            return original_locked(intent_id)

        with (
            patch("core.membership_arrival_recovery.checkout.confirm", side_effect=paused_confirm),
            patch("core.membership_arrival_recovery.locked", side_effect=checked_locked),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            first = pool.submit(self.run_in_connection, lambda: self.accept(uuid.uuid4()))
            self.assertTrue(created.wait(timeout=10))
            second = pool.submit(self.run_in_connection, lambda: self.accept(uuid.uuid4()))
            self.assertIsNotNone(first.result(timeout=20))
            self.assertIsNone(second.result(timeout=20))
        self.assertEqual(MembershipArrivalResolution.objects.count(), 1)
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)

    def test_started_owner_review_prevents_a_waiting_original_worker_from_charging(self):
        self.inputs()
        entering, proceed = Event(), Event()
        original_lock = membership_arrival_pending.lock_request

        def paused_lock(key):
            entering.set()
            if not proceed.wait(timeout=10):
                raise AssertionError("Owner confirmation did not release the original worker.")
            return original_lock(key)

        with (
            patch("core.membership_arrival_pending.lock_request", side_effect=paused_lock),
            ThreadPoolExecutor(max_workers=1) as pool,
        ):
            waiting = pool.submit(
                self.run_in_connection, lambda: membership_arrival_pending.complete(self.intent.pk)
            )
            self.assertTrue(entering.wait(timeout=10))
            accepted = self.accept(uuid.uuid4())
            proceed.set()
            self.assertEqual(waiting.result(timeout=20).status, "completed")
        self.assertEqual(MembershipArrivalResolution.objects.get().checkout_id, accepted.pk)
        self.assertEqual(PaymentOperation.objects.count(), 2)
