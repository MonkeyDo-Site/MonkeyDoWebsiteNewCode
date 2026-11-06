from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase

from core.models import AuditEvent, Booking, Customer, Session
from core.services import reserve_booking

NY = ZoneInfo("America/New_York")
NOW = datetime(2027, 3, 9, 10, tzinfo=NY)


def setup_records(test):
    test.actor = get_user_model().objects.create_user(username="test-staff", is_staff=True)
    test.actor.user_permissions.add(Permission.objects.get(codename="add_booking"))
    test.customer = Customer.objects.create(
        last_name="Test Family", phone="2025550100", email="test@example.invalid"
    )
    test.session = Session.objects.create(
        starts_at=NOW + timedelta(hours=1),
        ends_at=NOW + timedelta(hours=2, minutes=15),
        public=True,
        supervised_capacity=3,
    )


class ReservationTests(TestCase):
    def setUp(self):
        setup_records(self)

    def reserve(self, **kwargs):
        with patch("django.utils.timezone.now", return_value=NOW):
            return reserve_booking(
                actor=self.actor, customer=self.customer, session_id=self.session.pk, **kwargs
            )

    def test_accepted_booking_and_audit_are_atomic(self):
        booking = self.reserve(children=2, adults=1, babies=5)
        self.assertEqual(Booking.objects.count(), 1)
        event = AuditEvent.objects.get()
        self.assertEqual(event.record_id, str(booking.reference))
        self.assertEqual(event.actor, self.actor)

    def test_audit_failure_rolls_back_reservation(self):
        with patch(
            "core.services.AuditEvent.objects.create", side_effect=RuntimeError("test failure")
        ):
            with self.assertRaises(RuntimeError):
                self.reserve(children=2, adults=1)
        self.assertEqual(Booking.objects.count(), 0)

    def test_capacity_failure_creates_neither_booking_nor_audit(self):
        with self.assertRaises(ValidationError):
            self.reserve(children=36, adults=1)
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_combined_capacity_checked_for_requested_party(self):
        with self.assertRaises(ValidationError):
            self.reserve(children=30, adults=21)

    def test_invalid_counts_and_adult_rules(self):
        cases = [
            dict(children=-1, adults=1),
            dict(children=True, adults=1),
            dict(children=1.5, adults=1),
            dict(children=0, adults=0),
            dict(children=1, adults=0),
            dict(children=1, adults=1, supervised=True),
        ]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValidationError):
                self.reserve(**args)
        self.assertFalse(Booking.objects.exists())

    def test_supervised_capacity_and_start_time(self):
        with self.assertRaises(ValidationError):
            self.reserve(children=4, adults=0, supervised=True)
        with patch("django.utils.timezone.now", return_value=self.session.starts_at):
            with self.assertRaises(ValidationError):
                reserve_booking(
                    actor=self.actor,
                    customer=self.customer,
                    session_id=self.session.pk,
                    children=1,
                    adults=0,
                    supervised=True,
                )

    def test_permission_checked_before_write(self):
        actor = get_user_model().objects.create_user(username="no-permission")
        with self.assertRaises(PermissionError):
            reserve_booking(
                actor=actor,
                customer=self.customer,
                session_id=self.session.pk,
                children=1,
                adults=1,
            )
        self.assertFalse(Booking.objects.exists())

    def test_disabled_actor_denied(self):
        self.actor.is_active = False
        with self.assertRaises(PermissionError):
            self.reserve(children=1, adults=1)


@skipUnless(
    connection.vendor == "postgresql", "Row locking must be verified on PostgreSQL, not SQLite."
)
class ConcurrentReservationTests(TransactionTestCase):
    def setUp(self):
        setup_records(self)

    def test_two_requests_for_last_child_place_only_one_succeeds(self):
        self.session.child_capacity = 1
        self.session.supervised_capacity = 0
        self.session.save()
        ready = Barrier(2)
        actor_id, customer_id, session_id = self.actor.pk, self.customer.pk, self.session.pk

        def attempt():
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=actor_id)
                customer = Customer.objects.get(pk=customer_id)
                ready.wait(timeout=10)
                try:
                    reserve_booking(
                        actor=actor, customer=customer, session_id=session_id, children=1, adults=1
                    )
                    return "accepted"
                except ValidationError:
                    return "full"
            finally:
                connections.close_all()

        with (
            patch("django.utils.timezone.now", return_value=NOW),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertCountEqual(results, ["accepted", "full"])
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)
