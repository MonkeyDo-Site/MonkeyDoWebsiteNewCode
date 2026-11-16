from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.template import Context, Template
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.availability import NEW_YORK, availability
from core.date_display import display_date, display_strftime
from core.models import Booking, CalendarDate, Session
from core.recurring import generate_sessions, save_slot
from core.recurring_views import SlotForm
from tests import test_scheduling as scheduling_tests
from tests.helpers import verified_owner_login
from tests.test_owner_accounts import STORAGES

FRIDAY = datetime(2027, 3, 12, 10, tzinfo=NEW_YORK)
MOTZEI = datetime(2027, 3, 13, 20, tzinfo=NEW_YORK)


class BusinessDateTests(SimpleTestCase):
    def test_full_short_and_numeric_template_dates_use_shared_wording(self):
        value = date(2027, 3, 13)
        rendered = Template('{{ day|date:"l" }}|{{ day|date:"D" }}|{{ day|date:"Y-m-d" }}').render(
            Context({"day": value})
        )
        self.assertEqual(rendered, "Motzei Shabbos|Motzei Shabbos|2027-03-13")
        self.assertEqual(value.weekday(), 5)
        self.assertEqual(display_date(None, "l"), "")

    def test_new_york_weekday_is_used_across_utc_midnight_without_mutating_value(self):
        value = datetime(2027, 3, 14, 2, tzinfo=dt_timezone.utc)
        self.assertEqual(
            display_date(value, "l, Y-m-d g:i A"), "Motzei Shabbos, 2027-03-13 9:00 PM"
        )
        self.assertEqual(
            display_strftime(value, "%a %b %d, %Y %I:%M %p"), "Motzei Shabbos Mar 13, 2027 09:00 PM"
        )
        self.assertEqual(value.isoformat(), "2027-03-14T02:00:00+00:00")
        friday = datetime(2027, 3, 13, 2, tzinfo=dt_timezone.utc)
        self.assertEqual(display_date(friday, "l"), "Friday")

    def test_other_weekdays_and_weekly_choice_values_are_unchanged(self):
        self.assertEqual(display_date(date(2027, 3, 14), "l"), "Sunday")
        choices = list(SlotForm().fields["weekdays"].choices)
        self.assertEqual(choices[0], (6, "Sunday"))
        self.assertEqual(choices[-1], (5, "Motzei Shabbos"))
        self.assertNotIn("Saturday", str(choices))


@override_settings(CUSTOMER_TEST_BOOKING=True, STORAGES=STORAGES)
class MotzeiBookingTests(TestCase):
    create = scheduling_tests.SchedulingTests.create

    def setUp(self):
        scheduling_tests.SchedulingTests.setUp(self)
        clock = patch("django.utils.timezone.now", return_value=FRIDAY)
        clock.start()
        self.addCleanup(clock.stop)

    def session(self, **kwargs):
        return self.create(
            **{
                "starts_at": MOTZEI,
                "ends_at": MOTZEI + timedelta(minutes=75),
                "play_mode": "accompanied",
                "supervised_capacity": 0,
            }
            | kwargs
        )

    def test_public_booking_and_staff_records_share_wording_and_preserve_actual_session_time(self):
        session = self.session()
        self.assertTrue(availability(session)["available"])
        self.assertTrue(str(session).startswith("Motzei Shabbos"))
        response = self.client.get("/book/")
        self.assertContains(response, "Motzei Shabbos, March 13")
        self.assertNotContains(response, "Saturday")
        self.assertContains(response, f"/book/start/{session.pk}/")
        self.client.post(f"/book/start/{session.pk}/")
        self.client.post("/book/details/", {"visited": "yes", "phone": self.customer.phone})
        self.client.post("/book/details/", {"last_name": self.customer.last_name})
        self.assertContains(self.client.get("/book/details/"), "Motzei Shabbos, March 13, 2027")
        self.client.post(
            "/book/details/",
            {
                "play_type": "open",
                "children": 1,
                "adults": 1,
                "babies": 0,
                "socks": 0,
                "expected_method": "cash",
            },
        )
        flow = self.client.session["customer_test_booking"]
        response = self.client.post(
            "/book/details/", {"flow_key": flow["key"], "acknowledge_test": "on"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get("/book/receipt/"), "Motzei Shabbos, March 13, 2027")
        booking = Booking.objects.get()
        self.assertEqual(booking.session.starts_at, MOTZEI)
        self.client.force_login(self.staff)
        for path in (
            f"/staff/bookings/{booking.pk}/",
            f"/staff/bookings/{booking.pk}/edit/",
            f"/staff/customers/{self.customer.pk}/",
            "/staff/bookings/?start=2027-03-13&end=2027-03-13",
        ):
            response = self.client.get(path)
            self.assertContains(response, "Motzei Shabbos")
            self.assertNotContains(response, "Saturday")
        response = self.client.post(f"/staff/bookings/{booking.pk}/release/")
        self.assertContains(response, "Motzei Shabbos")
        with patch("django.utils.timezone.now", return_value=MOTZEI - timedelta(hours=2)):
            today_client = Client()
            today_client.force_login(self.staff)
            self.assertContains(today_client.get("/staff/today/"), "Motzei Shabbos")
        # Ordinary staff still cannot configure dated/weekly sessions.
        self.assertEqual(self.client.get("/staff/scheduling/").status_code, 403)

    def test_normal_horizon_closure_capacity_and_private_visibility_still_apply(self):
        session = self.session()
        state = availability(session, now=FRIDAY - timedelta(days=2))
        self.assertFalse(state["hidden"])
        self.assertEqual(state["label"], "Not yet open")
        Session.objects.filter(pk=session.pk).update(public=False)
        session.refresh_from_db()
        self.assertTrue(availability(session)["hidden"])
        self.assertNotContains(self.client.get("/book/"), "Motzei Shabbos")
        self.assertEqual(self.client.post(f"/book/start/{session.pk}/").status_code, 400)
        Session.objects.filter(pk=session.pk).update(public=True)
        session.refresh_from_db()
        rule = CalendarDate.objects.create(day=MOTZEI.date(), closed=True)
        self.assertEqual(availability(session)["label"], "Not Available")
        self.assertEqual(self.client.post(f"/book/start/{session.pk}/").status_code, 400)
        rule.closed = False
        rule.save()
        Booking.objects.create(customer=self.customer, session=session, children=35, adults=1)
        self.assertEqual(availability(session)["label"], "Fully booked")
        self.assertEqual(self.client.post(f"/book/start/{session.pk}/").status_code, 400)

    def test_owner_scheduling_and_generated_weekly_session_use_same_day_and_visibility(self):
        slot = save_slot(
            actor=self.owner,
            data={
                "label": "Evening play",
                "weekdays": [5],
                "starts_at": time(20),
                "ends_at": time(21, 15),
                "active": True,
                "public": True,
                "play_mode": "accompanied",
                "child_capacity": 35,
                "total_capacity": 50,
                "supervised_capacity": 0,
            },
        )
        results = generate_sessions(
            actor=self.owner, slot_ids=[slot.pk], from_day=MOTZEI.date(), through_day=MOTZEI.date()
        )
        self.assertEqual(results[0]["outcome"], "Created")
        session = Session.objects.get()
        self.assertEqual(session.starts_at, MOTZEI)
        self.assertTrue(availability(session)["available"])
        verified_owner_login(self.client, self.owner)
        for path in (
            "/staff/scheduling/?day=2027-03-13",
            "/staff/scheduling/weekly/",
            reverse("session_edit", args=[session.pk]),
        ):
            response = self.client.get(path)
            self.assertContains(response, "Motzei Shabbos")
            self.assertNotContains(response, "Saturday")
            self.assertNotContains(response, "sessions are backend-only")
        response = self.client.get("/staff/scheduling/?day=2027-03-13")
        self.assertTrue(response.context["sessions"][0]["visible"])
