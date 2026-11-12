from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings

from core.availability import NEW_YORK, availability, opening_time
from core.models import AuditEvent, Booking, Session, SiteSettings, WeeklySlot
from core.recurring import FIELDS, delete_slot, generate_sessions, save_horizon, save_slot
from core.scheduling import SESSION_FIELDS, save_session
from tests import test_scheduling as scheduling_tests
from tests.helpers import verified_owner_login
from tests.test_owner_accounts import STORAGES

NOW = scheduling_tests.NOW


@override_settings(STORAGES=STORAGES)
class RecurringTests(TestCase):
    setUp = scheduling_tests.SchedulingTests.setUp
    reserve = scheduling_tests.SchedulingTests.reserve
    close_day = scheduling_tests.SchedulingTests.close_day

    def slot(self, **changes):
        data = dict(
            label="PRIVATE WEEKLY LABEL",
            weekdays=[1],
            starts_at=time(18),
            ends_at=time(19, 15),
            active=True,
            public=True,
            play_mode="accompanied",
            child_capacity=35,
            total_capacity=50,
            supervised_capacity=0,
        )
        return save_slot(actor=self.owner, data=data | changes)

    def generate(self, slot, **changes):
        return generate_sessions(
            actor=self.owner,
            slot_ids=[slot.pk],
            from_day=NOW.date(),
            through_day=NOW.date(),
            **changes,
        )

    def change_slot(self, slot, **changes):
        return save_slot(
            actor=self.owner,
            pk=slot.pk,
            revision=slot.revision,
            data={field: getattr(slot, field) for field in FIELDS} | changes,
        )

    def test_default_templates_match_approved_days_and_times(self):
        rows = list(WeeklySlot.objects.all())
        self.assertEqual(len(rows), 4)
        self.assertEqual(
            [row.starts_at for row in rows], [time(11, 30), time(13), time(14, 30), time(16)]
        )
        self.assertTrue(all(row.weekdays == [0, 1, 2, 3, 4, 6] for row in rows))
        self.assertFalse(Session.objects.exists())

    def test_generation_is_repeatable_and_tracks_source(self):
        slot = self.slot()
        self.assertEqual(self.generate(slot)[0]["outcome"], "Created")
        session = Session.objects.get()
        self.assertTrue(session.recurring_managed)
        self.assertEqual(session.source_slot_id, slot.pk)
        self.assertEqual(session.source_day, NOW.date())
        self.generate(slot)
        self.assertEqual(Session.objects.count(), 1)
        self.assertFalse(Session.objects.get().closed)

    def test_updates_only_untouched_unbooked_generated_sessions(self):
        slot = self.slot()
        self.generate(slot)
        slot = self.change_slot(slot, child_capacity=30)
        self.generate(slot, update_existing=True)
        session = Session.objects.get()
        self.assertEqual(session.child_capacity, 30)
        self.assertEqual(session.source_revision, 2)
        self.reserve(session)
        slot = self.change_slot(slot, child_capacity=25)
        result = self.generate(slot, update_existing=True)
        self.assertEqual(result[0]["outcome"], "Preserved")
        session.refresh_from_db()
        self.assertEqual(session.child_capacity, 30)

    def test_manual_override_ends_management_and_is_never_overwritten(self):
        slot = self.slot()
        self.generate(slot)
        session = Session.objects.get()
        data = {field: getattr(session, field) for field in SESSION_FIELDS} | {"closed": True}
        save_session(actor=self.owner, pk=session.pk, revision=session.revision, data=data)
        session.refresh_from_db()
        self.assertFalse(session.recurring_managed)
        self.change_slot(slot, child_capacity=30)
        self.generate(slot, update_existing=True)
        session.refresh_from_db()
        self.assertTrue(session.closed)
        self.assertEqual(session.child_capacity, 35)

    def test_inactive_default_immediately_blocks_booking_and_generation_then_reopens(self):
        slot = self.slot()
        self.generate(slot)
        row = Session.objects.get()
        slot = self.change_slot(slot, active=False)
        self.assertTrue(availability(row)["hidden"])
        with self.assertRaises(ValidationError):
            self.reserve(row, actor=self.owner, override_capacity=True)
        with self.assertRaises(ValidationError):
            self.generate(slot, update_existing=True)
        self.assertFalse(Session.objects.get().closed)
        slot = self.change_slot(slot, active=True)
        self.assertTrue(availability(row)["available"])

    def test_delete_preserves_bookings_quotes_and_session_times(self):
        slot = self.slot()
        self.generate(slot)
        row = Session.objects.get()
        booking = self.reserve(row)
        original = (row.starts_at, row.ends_at, booking.session_id, booking.edit_version)
        quote = booking.quotes.get().snapshot
        delete_slot(actor=self.owner, pk=slot.pk, revision=slot.revision, expected_bookings=1)
        slot.refresh_from_db()
        row.refresh_from_db()
        booking.refresh_from_db()
        self.assertFalse(slot.active)
        self.assertIsNotNone(slot.archived_at)
        self.assertEqual(
            (row.starts_at, row.ends_at, booking.session_id, booking.edit_version), original
        )
        self.assertEqual(booking.quotes.get().snapshot, quote)
        self.assertFalse(booking.attendance)
        self.assertTrue(availability(row)["hidden"])
        with self.assertRaises(ValidationError):
            self.generate(slot)
        with self.assertRaises(ValidationError):
            self.change_slot(slot, active=True)
        self.assertTrue(AuditEvent.objects.filter(action="schedule.weekly_slot_deleted").exists())

    def test_deactivation_blocks_manual_sessions_without_overwriting_manual_closures(self):
        slot = self.slot()
        self.generate(slot)
        row = Session.objects.get()
        save_session(
            actor=self.owner,
            pk=row.pk,
            revision=row.revision,
            data={field: getattr(row, field) for field in SESSION_FIELDS} | {"closed": True},
        )
        slot = self.change_slot(slot, active=False)
        self.assertTrue(availability(row)["hidden"])
        self.change_slot(slot, active=True)
        row.refresh_from_db()
        self.assertTrue(row.closed)
        self.assertFalse(availability(row)["available"])

    def test_archive_confirmation_and_audit_are_atomic(self):
        slot = self.slot()
        self.generate(slot)
        self.reserve(Session.objects.get())
        with self.assertRaises(ValidationError):
            delete_slot(actor=self.owner, pk=slot.pk, revision=slot.revision, expected_bookings=0)
        with self.assertRaises(ValidationError):
            delete_slot(actor=self.owner, pk=slot.pk, revision=0, expected_bookings=1)
        with patch("core.recurring.AuditEvent.objects.create", side_effect=RuntimeError("test")):
            with self.assertRaises(RuntimeError):
                delete_slot(
                    actor=self.owner, pk=slot.pk, revision=slot.revision, expected_bookings=1
                )
        slot.refresh_from_db()
        self.assertTrue(slot.active)
        self.assertIsNone(slot.archived_at)
        self.assertEqual(Booking.objects.count(), 1)

    def test_deleted_empty_timing_can_be_recreated_and_removal_is_audited(self):
        slot = self.slot()
        self.generate(slot)
        old = Session.objects.get()
        old_id = old.pk
        delete_slot(actor=self.owner, pk=slot.pk, revision=slot.revision, expected_bookings=0)
        self.assertFalse(Session.objects.filter(pk=old_id).exists())
        event = AuditEvent.objects.get(action="schedule.weekly_slot_deleted")
        self.assertEqual(event.changes["removed_unused_generated_sessions"][0]["id"], old_id)
        self.assertEqual(
            event.changes["removed_unused_generated_sessions"][0]["starts_at"],
            old.starts_at.astimezone(NEW_YORK).isoformat(),
        )
        replacement = self.slot()
        result = self.generate(replacement)
        self.assertEqual(result[0]["outcome"], "Created")
        self.assertEqual(Session.objects.count(), 1)
        self.assertTrue(availability(Session.objects.get())["available"])

    def test_delete_retains_manually_edited_unbooked_sessions(self):
        slot = self.slot()
        self.generate(slot)
        row = Session.objects.get()
        save_session(
            actor=self.owner,
            pk=row.pk,
            revision=row.revision,
            data={f: getattr(row, f) for f in SESSION_FIELDS} | {"private_label": "Custom date"},
        )
        delete_slot(actor=self.owner, pk=slot.pk, revision=slot.revision, expected_bookings=0)
        row.refresh_from_db()
        self.assertEqual(row.private_label, "Custom date")
        self.assertTrue(availability(row)["hidden"])

    def test_failed_delete_audit_restores_unused_sessions(self):
        slot = self.slot()
        self.generate(slot)
        row = Session.objects.get()
        with patch("core.recurring.AuditEvent.objects.create", side_effect=RuntimeError("test")):
            with self.assertRaises(RuntimeError):
                delete_slot(
                    actor=self.owner, pk=slot.pk, revision=slot.revision, expected_bookings=0
                )
        self.assertTrue(Session.objects.filter(pk=row.pk).exists())
        slot.refresh_from_db()
        self.assertIsNone(slot.archived_at)

    def test_deleted_booked_timing_still_prevents_overlapping_generation(self):
        slot = self.slot()
        self.generate(slot)
        self.reserve(Session.objects.get())
        delete_slot(actor=self.owner, pk=slot.pk, revision=slot.revision, expected_bookings=1)
        replacement = self.slot()
        result = self.generate(replacement)
        self.assertEqual(result[0]["outcome"], "Preserved")
        self.assertEqual(Session.objects.count(), 1)

    def test_delete_view_requires_owner_confirmation_and_csrf(self):
        slot = self.slot()
        path = f"/staff/scheduling/weekly/{slot.pk}/delete/"
        self.staff.user_permissions.add(Permission.objects.get(codename="change_weeklyslot"))
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(path).status_code, 403)
        verified_owner_login(self.client, self.owner)
        self.assertContains(self.client.get(path), "currently 0 bookings")
        self.assertEqual(
            self.client.post(path, {"revision": slot.revision, "expected_bookings": 0}).status_code,
            200,
        )
        slot.refresh_from_db()
        self.assertIsNone(slot.archived_at)
        client = Client(enforce_csrf_checks=True)
        verified_owner_login(client, self.owner)
        self.assertEqual(client.post(path, {}).status_code, 403)
        self.assertEqual(
            self.client.post(
                path, {"revision": slot.revision, "expected_bookings": 0, "confirm": "on"}
            ).status_code,
            302,
        )
        self.assertNotContains(self.client.get("/staff/scheduling/weekly/"), slot.label)

    def test_generation_choices_only_include_active_defaults(self):
        from core.recurring_views import GenerationForm

        self.assertIn("Standard play 1:00 PM", str(GenerationForm()))
        self.assertNotIn("Standard play 13:00", str(GenerationForm()))
        slot = self.slot()
        self.change_slot(slot, active=False)
        form = GenerationForm(
            {"slots": [slot.pk], "from_day": NOW.date(), "through_day": NOW.date()}
        )
        self.assertFalse(form.is_valid())
        self.assertNotIn(slot.pk, form.fields["slots"].queryset.values_list("pk", flat=True))

    def test_independent_session_conflict_is_preserved_and_not_adopted(self):
        slot = self.slot()
        from core.recurring import local_time

        row = Session.objects.create(
            starts_at=local_time(NOW.date(), time(18)),
            ends_at=local_time(NOW.date(), time(19)),
            public=False,
        )
        self.assertEqual(self.generate(slot)[0]["outcome"], "Preserved")
        row.refresh_from_db()
        self.assertIsNone(row.source_slot_id)
        self.assertFalse(row.public)

    def test_date_closure_stays_effective_after_generation(self):
        slot = self.slot()
        self.close_day()
        self.generate(slot)
        row = Session.objects.get()
        self.assertFalse(availability(row)["available"])
        self.change_slot(slot, child_capacity=30)
        self.generate(slot, update_existing=True)
        self.assertFalse(availability(Session.objects.get())["available"])

    def test_backend_only_and_saturday_rules_survive_generation(self):
        slot = self.slot(weekdays=[5], public=False)
        saturday = NOW.date() + timedelta(days=4)
        generate_sessions(
            actor=self.owner, slot_ids=[slot.pk], from_day=saturday, through_day=saturday
        )
        self.assertTrue(availability(Session.objects.get())["hidden"])

    def test_invalid_weekdays_overlap_stale_revision_and_range(self):
        for days in [[], [1, 1], [7], [True]]:
            with self.assertRaises(ValidationError):
                self.slot(weekdays=days)
        slot = self.slot()
        with self.assertRaises(ValidationError):
            self.slot()
        self.change_slot(slot, label="Changed")
        with self.assertRaises(ValidationError):
            self.change_slot(slot, label="Stale")
        with self.assertRaises(ValidationError):
            generate_sessions(
                actor=self.owner,
                slot_ids=[slot.pk],
                from_day=NOW.date(),
                through_day=NOW.date() - timedelta(days=1),
            )

    def test_dst_gap_and_fold_roll_back_whole_generation(self):
        for day in [date(2027, 3, 14), date(2027, 11, 7)]:
            slot = self.slot(
                weekdays=[6],
                starts_at=time(2, 15) if day.month == 3 else time(1, 15),
                ends_at=time(3, 30),
            )
            with self.assertRaises(ValidationError):
                generate_sessions(
                    actor=self.owner, slot_ids=[slot.pk], from_day=day, through_day=day
                )
            self.assertFalse(Session.objects.exists())
            self.change_slot(slot, active=False)

    def test_audit_failure_rolls_back_generated_sessions(self):
        slot = self.slot()
        with patch("core.recurring.AuditEvent.objects.create", side_effect=RuntimeError("test")):
            with self.assertRaises(RuntimeError):
                self.generate(slot)
        self.assertFalse(Session.objects.exists())

    def test_horizon_range_stale_value_and_reset_confirmation(self):
        save_horizon(actor=self.owner, days=10, expected_days=1)
        self.assertEqual(SiteSettings.objects.get().booking_horizon_days, 10)
        with self.assertRaises(ValidationError):
            save_horizon(actor=self.owner, days=2, expected_days=1)
        with self.assertRaises(ValidationError):
            save_horizon(actor=self.owner, days=1, expected_days=10)
        save_horizon(actor=self.owner, days=1, expected_days=10, reset_confirmed=True)
        for days in [0, 11, True]:
            with self.assertRaises(ValidationError):
                save_horizon(actor=self.owner, days=days, expected_days=1)
        sunday = date(2027, 3, 14)
        self.assertEqual(opening_time(sunday, 1).date(), date(2027, 3, 12))
        self.assertEqual(opening_time(sunday, 10).date(), date(2027, 3, 4))

    def test_owner_only_guards_even_with_model_permissions_and_csrf(self):
        self.staff.user_permissions.add(
            Permission.objects.get(codename="change_weeklyslot"),
            Permission.objects.get(codename="change_sitesettings"),
        )
        self.client.force_login(self.staff)
        for path in [
            "/staff/scheduling/weekly/",
            "/staff/scheduling/weekly/new/",
            "/staff/scheduling/horizon/",
        ]:
            self.assertEqual(self.client.get(path).status_code, 403)
        with self.assertRaises(PermissionDenied):
            save_horizon(actor=self.staff, days=2, expected_days=1)
        client = Client(enforce_csrf_checks=True)
        verified_owner_login(client, self.owner)
        self.assertEqual(client.post("/staff/scheduling/weekly/", {}).status_code, 403)

    def test_owner_weekly_form_roundtrip(self):
        verified_owner_login(self.client, self.owner)
        response = self.client.post(
            "/staff/scheduling/weekly/new/",
            dict(
                label="Evening",
                weekdays=["1", "3"],
                starts_at="18:00",
                ends_at="19:15",
                active="on",
                visibility="private",
                play_mode="accompanied",
                child_capacity=35,
                total_capacity=50,
                supervised_capacity=0,
            ),
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertEqual(WeeklySlot.objects.get(label="Evening").weekdays, [1, 3])

    def test_program_session_preserved_even_if_management_flag_is_not_cleared(self):
        slot = self.slot()
        self.generate(slot)
        row = Session.objects.get()
        row.kind = "party"
        row.save(update_fields=["kind"])
        self.change_slot(slot, child_capacity=30)
        result = self.generate(slot, update_existing=True)
        row.refresh_from_db()
        self.assertEqual(result[0]["outcome"], "Preserved")
        self.assertEqual(row.kind, "party")
        self.assertEqual(row.child_capacity, 35)

    def test_revert_button_requires_confirmation_and_preserves_bookings(self):
        slot = self.slot()
        self.generate(slot)
        booking = self.reserve(Session.objects.get())
        saved_quote = booking.quotes.get().snapshot
        verified_owner_login(self.client, self.owner)
        self.client.post("/staff/scheduling/horizon/", {"days": 7, "expected_days": 1})
        response = self.client.post(
            "/staff/scheduling/horizon/", {"days": 7, "expected_days": 7, "reset_to_default": "1"}
        )
        self.assertContains(response, "Confirm reverting")
        self.assertEqual(SiteSettings.objects.get().booking_horizon_days, 7)
        response = self.client.post(
            "/staff/scheduling/horizon/",
            {"days": 7, "expected_days": 7, "reset_to_default": "1", "reset_confirmed": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SiteSettings.objects.get().booking_horizon_days, 1)
        booking.refresh_from_db()
        self.assertEqual(booking.edit_version, 1)
        self.assertEqual(booking.quotes.get().snapshot, saved_quote)

    def test_development_seed_does_not_overlap_owner_sessions(self):
        from io import StringIO

        from django.core.management import call_command

        row = Session.objects.create(
            starts_at=self.data["starts_at"], ends_at=self.data["ends_at"], public=False
        )
        call_command("seed_staging", stdout=StringIO())
        self.assertFalse(
            Session.objects.filter(
                starts_at__date=NOW.date(), starts_at__hour=11, starts_at__minute=30
            ).exists()
        )
        row.refresh_from_db()
        self.assertFalse(row.public)

    def test_delete_view_refreshes_warning_if_booking_arrives_after_preview(self):
        slot = self.slot()
        self.generate(slot)
        verified_owner_login(self.client, self.owner)
        path = f"/staff/scheduling/weekly/{slot.pk}/delete/"
        self.assertContains(self.client.get(path), "currently 0 bookings")
        self.reserve(Session.objects.get())
        response = self.client.post(
            path, {"revision": slot.revision, "expected_bookings": 0, "confirm": "on"}
        )
        self.assertContains(response, "booking count changed")
        self.assertContains(response, "currently 1 bookings")
        self.assertEqual(response.context["form"].initial["expected_bookings"], 1)
        slot.refresh_from_db()
        self.assertIsNone(slot.archived_at)

    def test_deleted_unused_session_rejects_stale_reservation_without_server_error(self):
        from core.services import reserve_booking

        slot = self.slot()
        self.generate(slot)
        row = Session.objects.get()
        delete_slot(actor=self.owner, pk=slot.pk, revision=slot.revision, expected_bookings=0)
        with self.assertRaisesMessage(ValidationError, "no longer available"):
            self.reserve(row)
        with self.assertRaisesMessage(ValidationError, "no longer available"):
            reserve_booking(
                actor=self.staff, customer=self.customer, session_id=row.pk, children=1, adults=1
            )
