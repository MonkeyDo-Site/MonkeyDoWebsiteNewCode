from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from core.models import Session
from core.recurring import generate_sessions
from tests import test_recurring as recurring_tests


@skipUnless(
    connection.vendor == "postgresql", "Recurring generation concurrency requires PostgreSQL."
)
class RecurringConcurrencyTests(TransactionTestCase):
    setUp = recurring_tests.RecurringTests.setUp
    slot = recurring_tests.RecurringTests.slot

    def test_concurrent_generation_never_duplicates_dated_sessions(self):
        slot = self.slot()
        ready = Barrier(2)

        def attempt(_):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.owner.pk)
                ready.wait(timeout=10)
                return generate_sessions(
                    actor=actor,
                    slot_ids=[slot.pk],
                    from_day=recurring_tests.NOW.date(),
                    through_day=recurring_tests.NOW.date(),
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(Session.objects.count(), 1)
        self.assertEqual(sum(item["outcome"] == "Created" for rows in results for item in rows), 1)
        self.assertTrue(Session.objects.get().recurring_managed)

    def test_delete_and_new_booking_cannot_both_succeed_with_a_stale_warning(self):
        import uuid

        from django.core.exceptions import ValidationError

        from core.booking_management import create_test_booking
        from core.models import Booking, Customer, WeeklySlot
        from core.recurring import delete_slot

        slot = self.slot()
        generate_sessions(
            actor=self.owner,
            slot_ids=[slot.pk],
            from_day=recurring_tests.NOW.date(),
            through_day=recurring_tests.NOW.date(),
        )
        row = Session.objects.get()
        ready = Barrier(2)

        def attempt(operation):
            close_old_connections()
            try:
                owner = get_user_model().objects.get(pk=self.owner.pk)
                ready.wait(timeout=10)
                try:
                    if operation == "delete":
                        delete_slot(
                            actor=owner, pk=slot.pk, revision=slot.revision, expected_bookings=0
                        )
                    else:
                        create_test_booking(
                            actor=owner,
                            customer=Customer.objects.get(pk=self.customer.pk),
                            session_id=row.pk,
                            children=1,
                            adults=1,
                            creation_key=uuid.uuid4(),
                        )
                    return True
                except ValidationError:
                    return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["delete", "book"]))
        self.assertEqual(sum(results), 1)
        archived = WeeklySlot.objects.get(pk=slot.pk).archived_at is not None
        self.assertEqual(Booking.objects.count(), 0 if archived else 1)
