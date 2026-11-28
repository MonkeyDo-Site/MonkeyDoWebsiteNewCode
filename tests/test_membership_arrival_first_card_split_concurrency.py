from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.db import close_old_connections, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from core import membership_arrival
from core.membership_records import MembershipArrivalIntent
from core.models import PaymentOperation
from tests import test_customer_credit_concurrency as races
from tests import test_membership_arrival_first_card_split as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class SplitFirstCardRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = races.CustomerCreditRaceTests.setUp
    prepare = fixtures.FirstSplitCardArrivalTests.prepare
    start = fixtures.FirstSplitCardArrivalTests.start
    accept = fixtures.FirstSplitCardArrivalTests.accept

    def test_overlapping_confirmation_preserves_one_manual_set_and_one_first_card_request(self):
        self.start()
        accepted = membership_arrival.review(**self.options)
        bought, waiting = Event(), Event()
        purchase, lock = membership_arrival.purchase, membership_arrival.lock_request

        def paused_purchase(**kw):
            member = purchase(**kw)
            bought.set()
            if not waiting.wait(timeout=10):
                raise AssertionError("Second request did not reach its lock")
            return member

        def checked_lock(key):
            if bought.is_set():
                waiting.set()
            return lock(key)

        def run():
            close_old_connections()
            try:
                return membership_arrival.confirm(
                    **self.options,
                    request_key=self.key,
                    reviewed_hash=accepted["fingerprint"],
                    confirmed=True,
                    accepted=True,
                    verified_received=True,
                ).pk
            finally:
                connections.close_all()

        with (
            patch("core.membership_arrival.purchase", side_effect=paused_purchase),
            patch("core.membership_arrival.lock_request", side_effect=checked_lock),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            first = pool.submit(run)
            self.assertTrue(bought.wait(timeout=10))
            second = pool.submit(run)
            self.assertEqual(first.result(timeout=20), second.result(timeout=20))
        self.assertEqual(MembershipArrivalIntent.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertEqual(PaymentOperation.objects.filter(tender="card").count(), 1)

    def test_reverse_refuses_used_split_arrival_scope(self):
        self.start()
        self.accept()
        with (
            self.assertRaisesMessage(RuntimeError, "Accepted split membership arrivals"),
            transaction.atomic(),
        ):
            MigrationExecutor(connection).migrate([("core", "0077_membership_booking_zelle")])
        self.assertEqual(MembershipArrivalIntent.objects.count(), 1)
        self.assertIn(
            ("core", "0078_split_membership_arrival"),
            MigrationExecutor(connection).loader.applied_migrations,
        )

    def test_unused_scope_reverses_restores_and_accepts_current_pending_card(self):
        try:
            MigrationExecutor(connection).migrate([("core", "0077_membership_booking_zelle")])
        finally:
            MigrationExecutor(connection).migrate([("core", "0085_paid_visit_received_split")])
        self.start()
        self.accept()
        self.assertEqual(MembershipArrivalIntent.objects.count(), 1)
