"""Overlapping final submissions cannot collect the combined payment twice."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.db import close_old_connections, connection, connections, transaction
from django.test import TransactionTestCase, override_settings

from core import membership_arrival
from core.communications.models import MessageDelivery
from core.membership_records import MembershipArrivalCheckout, MembershipPurchase
from core.models import PaymentOperation
from tests import test_customer_credit_concurrency as fixtures
from tests import test_membership_arrival as arrival_fixtures
from tests import test_membership_arrival_card as card_fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class CombinedArrivalRaceTests(InitialCreditFixtures, TransactionTestCase):
    setUp = fixtures.CustomerCreditRaceTests.setUp
    prepare = arrival_fixtures.CombinedMembershipArrivalTests.prepare

    def test_second_submission_waits_for_first_and_returns_its_completed_receipt(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL transaction/advisory-lock race")
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


@override_settings(**SETTINGS)
class CombinedVisitFundingRaceTests(InitialCreditFixtures, RuntimeRoleMixin, TransactionTestCase):
    setUp = fixtures.CustomerCreditRaceTests.setUp
    prepare = arrival_fixtures.CombinedMembershipArrivalTests.prepare
    card_visit = card_fixtures.CreditFundedCardArrivalTests.card_visit

    def test_committed_source_return_is_seen_after_dispatch_waits_for_customer_lock(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL dependent-dispatch funding race")
        from core.membership_reservations import lock_customer
        from core.payments.operations import begin_dispatch

        self.card_visit()
        correction_locked, dispatch_waiting = Event(), Event()

        def dispatch_lock(customer_id):
            dispatch_waiting.set()
            return lock_customer(customer_id)

        def correction():
            with transaction.atomic():
                lock_customer(self.customer.pk)
                correction_locked.set()
                if not dispatch_waiting.wait(timeout=10):
                    raise AssertionError("Dependent dispatch never reached its funding lock.")
                self.external_return(self.credit_source.operations.get(kind="receipt"))

        def run(fn):
            close_old_connections()
            try:
                return fn()
            finally:
                connections.close_all()

        with (
            patch("core.membership_arrival.lock_customer", side_effect=dispatch_lock),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            changed = pool.submit(run, correction)
            self.assertTrue(correction_locked.wait(timeout=10))
            dispatched = pool.submit(run, lambda: begin_dispatch(self.operation.pk))
            changed.result(timeout=20)
            self.assertIsNone(dispatched.result(timeout=20))
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.state, "cancelled")
        self.assertEqual(self.operation.result_code, "changed_before_dispatch")
