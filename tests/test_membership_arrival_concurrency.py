"""Overlapping final submissions cannot collect the combined payment twice."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings

from core import membership_arrival
from core.communications.models import MessageDelivery
from core.membership_records import MembershipArrivalCheckout, MembershipPurchase
from core.models import PaymentOperation
from tests import test_customer_credit_concurrency as fixtures
from tests import test_membership_arrival as arrival_fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures


@override_settings(**SETTINGS)
class CombinedArrivalRaceTests(InitialCreditFixtures, TransactionTestCase):
    setUp = fixtures.CustomerCreditRaceTests.setUp
    prepare = arrival_fixtures.CombinedMembershipArrivalTests.prepare

    def test_second_submission_waits_for_first_and_returns_its_completed_receipt(self):
        booking = self.prepare()
        accepted = membership_arrival.review(**self.options)
        bought, waiting = Event(), Event()
        original_purchase, original_lock = (
            membership_arrival.purchase,
            membership_arrival.lock_request,
        )

        def paused_purchase(**kwargs):
            member = original_purchase(**kwargs)
            bought.set()
            if not waiting.wait(timeout=10):
                raise AssertionError("The second confirmation never reached its request lock.")
            return member

        def checked_lock(key):
            if bought.is_set():
                waiting.set()
            return original_lock(key)

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
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "arrived")
        self.assertEqual(MembershipArrivalCheckout.objects.count(), 1)
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 2)
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").count(), 1
        )
