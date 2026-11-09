import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings

from core.models import Booking, BookingQuote, Customer, PricingPolicy, Session
from core.public_booking import review_quote, submit_booking


@skipUnless(connection.vendor == "postgresql", "PostgreSQL concurrency check")
@override_settings(CUSTOMER_TEST_BOOKING=True)
class PublicBookingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 8, 14, tzinfo=dt_timezone.utc)
        timer = patch("django.utils.timezone.now", return_value=self.now)
        timer.start()
        self.addCleanup(timer.stop)
        PricingPolicy.objects.create()
        self.slot = Session.objects.create(
            starts_at=self.now + timedelta(hours=2),
            ends_at=self.now + timedelta(hours=3, minutes=15),
            public=True,
            child_capacity=1,
            total_capacity=3,
        )

    def flow(self, n):
        flow = {
            "key": str(uuid.uuid4()),
            "session_id": self.slot.pk,
            "expires": self.now.timestamp() + 1200,
            "stage": "review",
            "phone": f"20255501{n:02}",
            "contact": {"last_name": f"Test {n}", "email": f"test{n}@example.invalid"},
        }
        data = {
            "children": 1,
            "adults": 1,
            "babies": 0,
            "socks": 0,
            "supervised": False,
            "expected_method": "cash",
            "referral_source": "",
        }
        flow["details"] = data
        flow["quote"] = review_quote(flow, data)
        return flow

    def run_pair(self, flows):
        barrier = Barrier(2)

        def run(flow):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return submit_booking(flow).pk
            except ValidationError:
                return None
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, flows))

    def test_two_public_customers_compete_for_one_place_without_orphan_customer(self):
        results = self.run_pair([self.flow(1), self.flow(2)])
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(BookingQuote.objects.count(), 1)

    def test_concurrent_repeat_submission_creates_one_customer_and_booking(self):
        flow = self.flow(3)
        results = self.run_pair([flow, flow])
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(Customer.objects.count(), 1)
