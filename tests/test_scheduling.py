import uuid
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings

from core.availability import availability
from core.booking_management import create_test_booking, move_test_booking
from core.models import AuditEvent, Booking, CalendarDate, Customer, Session
from core.scheduling import SESSION_FIELDS, save_date, save_session
from core.scheduling_views import SessionForm
from core.services import reserve_booking
from tests.helpers import verified_owner_login
from tests.test_customers import staff_user
from tests.test_owner_accounts import STORAGES

NY = ZoneInfo("America/New_York")
NOW = datetime(2027, 3, 9, 10, tzinfo=NY)


@override_settings(STORAGES=STORAGES)
class SchedulingTests(TestCase):
    def setUp(self):
        clock = patch("django.utils.timezone.now", return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)
        self.owner = staff_user("owner", owner=True)
        self.staff = staff_user()
        self.customer = Customer.objects.create(
            last_name="Test", phone="2025550122", email="test@example.invalid"
        )
        self.data = dict(
            starts_at=NOW + timedelta(hours=1),
            ends_at=NOW + timedelta(hours=2, minutes=15),
            public=True,
            closed=False,
            private_label="PRIVATE INTERNAL LABEL",
            play_mode="both",
            child_capacity=35,
            total_capacity=50,
            supervised_capacity=3,
        )

    def create(self, **changes):
        return save_session(actor=self.owner, data=self.data | changes)

    def close_day(self, **changes):
        args = dict(
            actor=self.owner,
            day=NOW.date(),
            closed=True,
            private_reason="PRIVATE CLOSURE REASON",
            chol_hamoed=False,
            revision=0,
        )
        return save_date(**(args | changes))

    def reserve(self, session, **changes):
        args = dict(
            actor=self.staff,
            customer=self.customer,
            session_id=session.pk,
            children=1,
            adults=1,
            creation_key=uuid.uuid4(),
        )
        return create_test_booking(**(args | changes))

    def test_owner_create_and_edit_are_audited(self):
        session = self.create()
        save_session(
            actor=self.owner, pk=session.pk, revision=1, data=self.data | {"public": False}
        )
        session.refresh_from_db()
        self.assertFalse(session.public)
        self.assertEqual(session.revision, 2)
        self.assertEqual(AuditEvent.objects.filter(record_type="session").count(), 2)
        with self.assertRaises(ValidationError):
            save_session(actor=self.owner, pk=session.pk, revision=1, data=self.data)

    def test_closure_blocks_both_reservation_paths_and_never_leaks_reason(self):
        session = self.create()
        self.close_day()
        self.assertEqual(availability(session)["label"], "Unavailable")
        with self.assertRaises(ValidationError):
            self.reserve(session)
        with self.assertRaises(ValidationError):
            reserve_booking(
                actor=self.staff,
                customer=self.customer,
                session_id=session.pk,
                children=1,
                adults=1,
            )
        response = self.client.get("/book/")
        self.assertContains(response, "Unavailable")
        self.assertNotContains(response, "PRIVATE CLOSURE REASON")
        self.assertNotContains(response, "PRIVATE INTERNAL LABEL")
        self.assertFalse(Booking.objects.exists())

    def test_close_preserves_bookings_quotes_then_reopen_restores_availability(self):
        session = self.create()
        booking = self.reserve(session)
        quote = booking.quotes.get().snapshot
        self.close_day(chol_hamoed=True)
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "")
        self.assertEqual(booking.quotes.get().snapshot, quote)
        self.close_day(closed=False, revision=1, private_reason="", chol_hamoed=True)
        self.assertTrue(availability(session)["available"])
        self.assertTrue(CalendarDate.objects.get().chol_hamoed)

    def test_closure_also_blocks_new_sessions_and_owner_booking_override(self):
        self.close_day()
        session = self.create()
        with self.assertRaises(ValidationError):
            self.reserve(session, actor=self.owner, override_capacity=True)

    def test_date_revision_and_reason_required(self):
        with self.assertRaises(ValidationError):
            self.close_day(private_reason=" ")
        self.assertFalse(CalendarDate.objects.exists())
        self.close_day()
        with self.assertRaises(ValidationError):
            self.close_day()
        self.assertEqual(CalendarDate.objects.get().revision, 1)

    def test_dates_bounded_to_two_years_and_no_overnight_or_overlap(self):
        for delta in [-1, 732]:
            with self.assertRaises(ValidationError):
                self.close_day(day=NOW.date() + timedelta(days=delta))
        with self.assertRaises(ValidationError):
            self.create(ends_at=NOW + timedelta(days=1))
        self.create()
        with self.assertRaises(ValidationError):
            self.create(starts_at=NOW + timedelta(hours=1, minutes=1))
        self.assertEqual(Session.objects.count(), 1)

    def test_booked_times_and_capacity_are_protected(self):
        session = self.create()
        self.reserve(session, children=4)
        for changes in [
            {"starts_at": self.data["starts_at"] + timedelta(minutes=1)},
            {"child_capacity": 3},
            {"play_mode": "supervised"},
        ]:
            with self.assertRaises(ValidationError):
                save_session(actor=self.owner, pk=session.pk, revision=1, data=self.data | changes)
        session.refresh_from_db()
        self.assertEqual(session.revision, 1)
        save_session(actor=self.owner, pk=session.pk, revision=1, data=self.data | {"closed": True})
        session.refresh_from_db()
        self.assertTrue(session.closed)
        self.assertEqual(Booking.objects.count(), 1)

    def test_play_mode_cannot_be_bypassed(self):
        session = self.create(play_mode="supervised")
        with self.assertRaises(ValidationError):
            self.reserve(session)
        self.reserve(session, supervised=True, adults=0)
        self.assertFalse(availability(session)["accompanied_available"])

    def test_move_into_closed_date_preserves_original(self):
        session = self.create()
        booking = self.reserve(session)
        target = self.create(
            starts_at=NOW + timedelta(days=1, hours=1), ends_at=NOW + timedelta(days=1, hours=2)
        )
        self.close_day(day=target.starts_at.date())
        with self.assertRaises(ValidationError):
            move_test_booking(
                actor=self.staff, booking_id=booking.pk, version=1, session_id=target.pk
            )
        booking.refresh_from_db()
        self.assertEqual(booking.session_id, session.pk)

    def test_staff_denied_even_with_model_permissions(self):
        from django.contrib.auth.models import Permission

        self.staff.user_permissions.add(
            Permission.objects.get(codename="change_session", content_type__app_label="core"),
            Permission.objects.get(codename="change_calendardate"),
        )
        self.client.force_login(self.staff)
        for path in ["/staff/scheduling/", "/staff/scheduling/new/", "/staff/scheduling/date/"]:
            self.assertEqual(self.client.get(path).status_code, 403)
        with self.assertRaises(PermissionDenied):
            save_session(actor=self.staff, data=self.data)
        with self.assertRaises(PermissionDenied):
            self.close_day(actor=self.staff)

    def test_owner_form_roundtrip_and_csrf(self):
        verified_owner_login(self.client, self.owner)
        response = self.client.post(
            "/staff/scheduling/new/",
            {
                **self.data,
                "starts_at": "2027-03-09T11:00",
                "ends_at": "2027-03-09T12:15",
                "visibility": "public",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        session = Session.objects.get()
        self.assertEqual(session.starts_at.astimezone(NY).hour, 11)
        client = Client(enforce_csrf_checks=True)
        verified_owner_login(client, self.owner)
        self.assertEqual(client.post("/staff/scheduling/date/?day=2027-03-09", {}).status_code, 403)

    def test_dst_gap_and_ambiguous_times_rejected_by_form(self):
        for stamp in ["2027-03-14T02:15", "2027-11-07T01:15"]:
            form = SessionForm(
                {**self.data, "starts_at": stamp, "ends_at": stamp, "visibility": "public"}
            )
            self.assertFalse(form.is_valid())
            self.assertIn("starts_at", form.errors)

    def test_audit_failure_rolls_back_calendar_change(self):
        with patch("core.scheduling.AuditEvent.objects.create", side_effect=RuntimeError("test")):
            with self.assertRaises(RuntimeError):
                self.close_day()
        self.assertFalse(CalendarDate.objects.exists())

    def test_edit_form_keeps_private_fields_owner_only(self):
        session = self.create()
        verified_owner_login(self.client, self.owner)
        response = self.client.get(f"/staff/scheduling/{session.pk}/")
        self.assertContains(response, "PRIVATE INTERNAL LABEL")
        self.assertEqual(set(SESSION_FIELDS) - {"public"}, set(SessionForm.Meta.fields))

    def test_legacy_zero_supervised_limit_can_be_made_explicit_without_moving_booking(self):
        session = Session.objects.create(
            starts_at=self.data["starts_at"], ends_at=self.data["ends_at"], supervised_capacity=0
        )
        self.reserve(session)
        data = self.data | {"play_mode": "accompanied", "supervised_capacity": 0, "closed": True}
        save_session(actor=self.owner, pk=session.pk, revision=1, data=data)
        session.refresh_from_db()
        self.assertTrue(session.closed)
        self.assertEqual(session.play_mode, "accompanied")

    def test_supervised_only_public_slot_closes_at_its_own_limit_and_start(self):
        session = self.create(play_mode="supervised")
        self.reserve(session, supervised=True, children=3, adults=0)
        self.assertEqual(availability(session)["label"], "Fully booked")
        self.assertFalse(availability(session, now=session.starts_at)["available"])

    def test_edit_session_uses_time_only_inputs_and_fixed_date(self):
        session = self.create()
        verified_owner_login(self.client, self.owner)
        response = self.client.get(f"/staff/scheduling/{session.pk}/")
        self.assertContains(response, "Session date:")
        self.assertNotContains(response, 'type="datetime-local"')
        form = SessionForm(
            {
                **self.data,
                "starts_at": "11:05 AM",
                "ends_at": "12:20 PM",
                "visibility": "public",
                "revision": 1,
            },
            instance=session,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["starts_at"].astimezone(NY).date(), NOW.date())
        response = self.client.post(
            f"/staff/scheduling/{session.pk}/",
            {
                **self.data,
                "starts_at": "11:05 AM",
                "ends_at": "12:20 PM",
                "visibility": "public",
                "revision": 1,
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        session.refresh_from_db()
        self.assertEqual(session.starts_at.astimezone(NY).minute, 5)
        self.assertEqual(session.starts_at.astimezone(NY).date(), NOW.date())

    def test_date_form_ignores_forged_day_and_session_service_rejects_date_move(self):
        session = self.create()
        with self.assertRaisesMessage(ValidationError, "only the timing"):
            save_session(
                actor=self.owner,
                pk=session.pk,
                revision=session.revision,
                data=self.data
                | {
                    "starts_at": self.data["starts_at"] + timedelta(days=1),
                    "ends_at": self.data["ends_at"] + timedelta(days=1),
                },
            )
        verified_owner_login(self.client, self.owner)
        response = self.client.post(
            f"/staff/scheduling/date/?day={NOW.date().isoformat()}",
            {
                "day": (NOW.date() + timedelta(days=1)).isoformat(),
                "revision": 0,
                "chol_hamoed": "on",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertEqual(CalendarDate.objects.get().day, NOW.date())
