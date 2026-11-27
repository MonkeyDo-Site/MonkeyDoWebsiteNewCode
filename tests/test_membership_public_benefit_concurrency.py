"""Concurrent receipt actions cannot reserve one daily benefit twice."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings

from core import membership_public_benefits as benefits
from core.models import PaymentOperation
from core.public_booking import submit_booking
from tests import test_customer_credit_concurrency as race_fixtures
from tests import test_membership_public_benefits as fixtures
from tests.test_membership_initial_credit import SETTINGS


@override_settings(**SETTINGS)
class PublicBenefitRaceTests(fixtures.AvailableBenefitFixtures, TransactionTestCase):
    setUp = race_fixtures.CustomerCreditRaceTests.setUp

    def apply_in_thread(self, values):
        close_old_connections()
        try:
            return benefits.confirm(**values).pk
        finally:
            connections.close_all()

    def test_duplicate_confirmation_waits_and_returns_one_reserved_quote(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL request/booking/customer locks")
        booking = self.available()
        values = self.accepted()
        before = PaymentOperation.objects.count()
        prepared, waiting = Event(), Event()
        reserve, lock = benefits.reserve, benefits.lock_request

        def paused(**kwargs):
            prepared.set()
            if not waiting.wait(timeout=10):
                raise AssertionError("The duplicate never reached its request lock.")
            return reserve(**kwargs)

        def request_lock(key):
            if prepared.is_set():
                waiting.set()
            return lock(key)

        with (
            patch("core.membership_public_benefits.reserve", side_effect=paused),
            patch("core.membership_public_benefits.lock_request", side_effect=request_lock),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            first = pool.submit(self.apply_in_thread, values)
            self.assertTrue(prepared.wait(timeout=10))
            second = pool.submit(self.apply_in_thread, values)
            self.assertEqual(first.result(timeout=20), second.result(timeout=20))
        booking.refresh_from_db()
        self.assertEqual(booking.edit_version, 2)
        self.assertEqual(booking.quotes.count(), 2)
        self.assertEqual(booking.membership_benefits.count(), 1)
        self.assertEqual(booking.membership_benefits.get().current.status, "reserved")
        self.assertEqual(PaymentOperation.objects.count(), before)

    def test_two_bookings_can_apply_only_one_released_daily_place(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL customer reservation locks")
        second = self.available(release=False)
        third_flow = self.ready()
        third = submit_booking(third_flow)
        third_flow.update(stage="done", booking_id=third.pk)
        self.act(self.first, dict(method="card", charge_fee=False), kind="cancellation")
        first_values = self.accepted()
        self.flow_data = third_flow
        second_values = self.accepted()
        start = Barrier(2)
        before = PaymentOperation.objects.count()

        def competing(values):
            start.wait(timeout=10)
            try:
                return self.apply_in_thread(values)
            except ValidationError:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(competing, values) for values in (first_values, second_values)]
            results = [job.result(timeout=20) for job in jobs]
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(second.membership_benefits.count() + third.membership_benefits.count(), 1)
        self.assertEqual(sorted([second.quotes.count(), third.quotes.count()]), [1, 2])
        self.assertEqual(PaymentOperation.objects.count(), before)
