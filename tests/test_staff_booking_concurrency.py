import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from core.booking_management import create_test_booking, edit_test_booking
from core.models import Booking, BookingQuote, PricingPolicy
from tests.test_staff_bookings import StaffBookingTests


@skipUnless(connection.vendor == "postgresql", "Row-lock concurrency requires PostgreSQL.")
class StaffBookingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        StaffBookingTests.setUp(self)
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()

    def parallel(self, operation):
        barrier = Barrier(2)

        def run(i):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.staff.pk)
                barrier.wait(timeout=10)
                try:
                    return operation(actor, i).pk
                except ValidationError:
                    return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, range(2)))

    def create(self, actor, key):
        return create_test_booking(
            actor=actor,
            customer=self.customer,
            session_id=self.session.pk,
            children=1,
            adults=1,
            creation_key=key,
        )

    def test_last_place_cannot_be_sold_twice(self):
        self.session.child_capacity = 1
        self.session.supervised_capacity = 1
        self.session.save()
        results = self.parallel(lambda actor, i: self.create(actor, uuid.uuid4()))
        self.assertEqual(results.count(None), 1)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(BookingQuote.objects.count(), 1)

    def test_same_submission_creates_one_booking_and_quote(self):
        key = uuid.uuid4()
        results = self.parallel(lambda actor, i: self.create(actor, key))
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(BookingQuote.objects.count(), 1)

    def test_two_edits_cannot_overwrite_same_revision(self):
        booking = self.create(self.staff, uuid.uuid4())
        results = self.parallel(
            lambda actor, i: edit_test_booking(
                actor=actor,
                booking_id=booking.pk,
                version=1,
                children=2 + i,
                adults=1,
                babies=0,
                socks=0,
                expected_method="card",
            )
        )
        self.assertEqual(results.count(None), 1)
        self.assertEqual(BookingQuote.objects.count(), 2)
