import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections, transaction
from django.test import TransactionTestCase

from core.booking_management import create_test_booking
from core.calendar import lock_calendar
from core.models import Booking, CalendarDate, PricingPolicy, Session
from core.scheduling import save_date, save_session
from tests.test_scheduling import NOW, SchedulingTests


@skipUnless(connection.vendor == "postgresql", "Calendar concurrency requires PostgreSQL.")
class SchedulingConcurrencyTests(TransactionTestCase):
    setUp = SchedulingTests.setUp

    def attempt(self, operation):
        close_old_connections()
        try:
            actor = get_user_model().objects.get(pk=self.owner.pk)
            try:
                return operation(actor)
            except ValidationError:
                return None
        finally:
            connections.close_all()

    def test_competing_sessions_cannot_overlap(self):
        ready = Barrier(2)

        def create(actor):
            ready.wait(timeout=10)
            return save_session(actor=actor, data=self.data).pk

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.attempt(create), range(2)))
        self.assertEqual(results.count(None), 1)
        self.assertEqual(Session.objects.count(), 1)

    def test_competing_date_changes_reject_stale_editor(self):
        ready = Barrier(2)

        def change(actor):
            ready.wait(timeout=10)
            return save_date(
                actor=actor,
                day=NOW.date(),
                closed=True,
                private_reason="Test closure",
                chol_hamoed=False,
                revision=0,
            ).pk

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.attempt(change), range(2)))
        self.assertEqual(results.count(None), 1)
        self.assertEqual(CalendarDate.objects.get().revision, 1)

    def test_waiting_reservation_observes_committed_closure(self):
        if not PricingPolicy.objects.exists():
            PricingPolicy.objects.create()
        session = save_session(actor=self.owner, data=self.data)
        held = Event()
        release = Event()

        def closing(actor):
            with transaction.atomic():
                lock_calendar(exclusive=True)
                held.set()
                if not release.wait(timeout=10):
                    raise RuntimeError("Test did not release calendar lock")
                return save_date(
                    actor=actor,
                    day=NOW.date(),
                    closed=True,
                    private_reason="Closed",
                    chol_hamoed=False,
                    revision=0,
                ).pk

        def reserve(actor):
            return create_test_booking(
                actor=actor,
                customer=self.customer,
                session_id=session.pk,
                children=1,
                adults=1,
                creation_key=uuid.uuid4(),
            ).pk

        with ThreadPoolExecutor(max_workers=2) as pool:
            closing_result = pool.submit(self.attempt, closing)
            self.assertTrue(held.wait(timeout=10))
            reservation = pool.submit(self.attempt, reserve)
            release.set()
            self.assertIsNotNone(closing_result.result(timeout=10))
            self.assertIsNone(reservation.result(timeout=10))
        self.assertFalse(Booking.objects.exists())
