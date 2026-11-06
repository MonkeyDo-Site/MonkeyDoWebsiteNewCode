from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase

from core.availability import availability, occupancy, opening_time
from core.models import Booking, Customer, Session

NY = ZoneInfo("America/New_York")


class OpeningTests(TestCase):
    def test_regular_date_opens_previous_calendar_midnight(self):
        self.assertEqual(opening_time(date(2027, 3, 9), 1), datetime(2027, 3, 8, tzinfo=NY))

    def test_sunday_opens_friday_and_longer_horizon_can_open_earlier(self):
        self.assertEqual(opening_time(date(2027, 3, 14), 1), datetime(2027, 3, 12, tzinfo=NY))
        self.assertEqual(opening_time(date(2027, 3, 14), 5), datetime(2027, 3, 9, tzinfo=NY))

    def test_dst_is_calendar_based_not_24_hours(self):
        opens = opening_time(date(2027, 3, 15), 1)
        self.assertEqual(opens.utcoffset(), timedelta(hours=-5))
        fall = opening_time(date(2027, 11, 8), 1)
        self.assertEqual(fall.utcoffset(), timedelta(hours=-4))

    def test_horizon_range(self):
        for value in (0, 11):
            with self.assertRaises(ValueError):
                opening_time(date(2027, 3, 9), value)


class AvailabilityTests(TestCase):
    def setUp(self):
        self.start = datetime(2027, 3, 9, 11, 30, tzinfo=NY)
        self.session = Session.objects.create(
            starts_at=self.start,
            ends_at=self.start + timedelta(minutes=75),
            public=True,
            supervised_capacity=5,
        )
        self.customer = Customer.objects.create(
            last_name="Test Family", phone="2025550100", email="test@example.invalid"
        )

    def book(self, **kwargs):
        return Booking.objects.create(customer=self.customer, session=self.session, **kwargs)

    def test_ordinary_stays_open_after_start_but_supervised_closes(self):
        state = availability(self.session, now=self.start + timedelta(minutes=1))
        self.assertTrue(state["available"])
        self.assertFalse(state["supervised_available"])
        self.assertFalse(availability(self.session, now=self.session.ends_at)["available"])

    def test_not_yet_open(self):
        self.assertEqual(
            availability(self.session, now=datetime(2027, 3, 7, tzinfo=NY))["label"], "Not yet open"
        )

    def test_child_limit_and_babies_exclusion(self):
        self.book(children=35, adults=1, babies=10)
        self.assertEqual(availability(self.session, now=self.start)["label"], "Fully booked")
        self.assertEqual(occupancy(self.session), (35, 1, 0))

    def test_combined_limit(self):
        self.book(children=25, adults=25)
        self.assertEqual(availability(self.session, now=self.start)["label"], "Fully booked")

    def test_cancelled_booking_releases_capacity(self):
        self.book(children=35, adults=15, attendance="cancelled")
        self.assertTrue(availability(self.session, now=self.start)["available"])

    def test_party_label_and_private_reason_never_exposed(self):
        self.session.kind = Session.Kind.PARTY
        self.session.private_label = "Private customer details"
        state = availability(self.session, now=self.start)
        self.assertEqual(state["label"], "A party is booked for this slot.")
        self.assertNotIn("Private", str(state))

    def test_saturday_and_backend_only_are_hidden(self):
        self.session.public = False
        self.assertTrue(availability(self.session, now=self.start)["hidden"])
        self.session.public = True
        self.session.starts_at = datetime(2027, 3, 13, 11, 30, tzinfo=NY)
        self.session.ends_at = self.session.starts_at + timedelta(minutes=75)
        self.assertTrue(availability(self.session, now=self.start)["hidden"])

    def test_supervised_subset_does_not_add_capacity(self):
        self.book(children=5, adults=0, supervised=True)
        state = availability(self.session, now=self.start - timedelta(minutes=5))
        self.assertTrue(state["available"])
        self.assertFalse(state["supervised_available"])
