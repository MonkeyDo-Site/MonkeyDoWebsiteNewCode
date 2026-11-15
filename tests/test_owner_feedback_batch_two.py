"""Owner-approved second batch: schedule transactions, filtering and identity rules."""

import uuid
from datetime import time, timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, SimpleTestCase, TestCase, override_settings

from core.availability import availability
from core.booking_forms import TestBookingForm
from core.booking_management import edit_test_booking
from core.customers import create_customer, update_customer
from core.memberships import create_draft
from core.models import AuditEvent, Booking, Customer, OwnerNotice, Session, WeeklySlot
from core.name_matching import similar_name
from core.recurring import FIELDS, generate_sessions, save_slot, save_slots
from core.templatetags.scheduling_labels import display_session_label
from tests import test_public_booking as public_tests
from tests import test_scheduling as scheduling_tests
from tests.helpers import verified_owner_login
from tests.test_owner_accounts import STORAGES

NOW = scheduling_tests.NOW


@override_settings(STORAGES=STORAGES)
class ScheduleBatchTests(TestCase):
    setUp = scheduling_tests.SchedulingTests.setUp
    reserve = scheduling_tests.SchedulingTests.reserve

    def slots(self):
        result = []
        for hour in range(18, 22):
            result.append(
                save_slot(
                    actor=self.owner,
                    data=dict(
                        label=f"Evening {hour}",
                        weekdays=[1],
                        starts_at=time(hour),
                        ends_at=time(hour, 45),
                        active=True,
                        public=True,
                        play_mode="accompanied",
                        child_capacity=35,
                        total_capacity=50,
                        supervised_capacity=0,
                    ),
                )
            )
        return result

    def generate(self, slots, **kwargs):
        return generate_sessions(
            actor=self.owner,
            slot_ids=[s.pk for s in slots],
            from_day=NOW.date(),
            through_day=NOW.date(),
            **kwargs,
        )

    def edits(self, slots, hours):
        return [
            {
                "pk": row.pk,
                "revision": row.revision,
                "data": {
                    **{f: getattr(row, f) for f in FIELDS},
                    "starts_at": time(hour),
                    "ends_at": time(hour, 45),
                },
            }
            for row, hour in zip(slots, hours)
        ]

    def test_four_slot_swap_preserves_identity_and_correct_audit(self):
        slots = self.slots()
        self.generate(slots)
        ids = dict(Session.objects.values_list("source_slot_id", "pk"))
        changed = save_slots(actor=self.owner, edits=self.edits(slots, [19, 20, 21, 18]))
        results = self.generate(changed, update_existing=True)
        self.assertEqual([r["outcome"] for r in results], ["Updated"] * 4)
        self.assertEqual(dict(Session.objects.values_list("source_slot_id", "pk")), ids)
        self.assertEqual(
            [
                Session.objects.get(source_slot=s).starts_at.astimezone(NOW.tzinfo).hour
                for s in slots
            ],
            [19, 20, 21, 18],
        )
        audits = AuditEvent.objects.filter(action="schedule.session_updated")
        self.assertEqual(audits.count(), 4)
        self.assertTrue(all("9000" not in str(e.changes) for e in audits))

    def test_invalid_final_overlap_and_stale_revision_leave_entire_schedule_unchanged(self):
        slots = self.slots()
        for edits in (self.edits(slots, [19, 19, 21, 22]), self.edits(slots, [19, 20, 21, 22])):
            if edits[0]["data"]["starts_at"] != edits[1]["data"]["starts_at"]:
                edits[-1]["revision"] = 999
            with self.assertRaises(ValidationError):
                save_slots(actor=self.owner, edits=edits)
            self.assertEqual(
                list(
                    WeeklySlot.objects.filter(pk__in=[s.pk for s in slots])
                    .order_by("pk")
                    .values_list("starts_at", flat=True)
                ),
                [time(h) for h in range(18, 22)],
            )

    def test_preserved_booked_session_cascades_conflict_without_partial_corruption(self):
        slots = self.slots()
        self.generate(slots)
        original = list(Session.objects.order_by("pk").values_list("pk", "starts_at"))
        self.reserve(Session.objects.get(source_slot=slots[0]))
        changed = save_slots(actor=self.owner, edits=self.edits(slots, [19, 20, 21, 18]))
        results = self.generate(changed, update_existing=True)
        self.assertEqual(
            list(Session.objects.order_by("pk").values_list("pk", "starts_at")), original
        )
        self.assertEqual(len(results), 4)
        self.assertTrue(any("booking history" in r["reason"] for r in results))
        self.assertTrue(any(r.get("conflicts") for r in results))

    def test_generation_audit_failure_rolls_back_temporary_parking_and_updates(self):
        slots = self.slots()
        self.generate(slots)
        original = list(Session.objects.order_by("pk").values_list("starts_at", flat=True))
        changed = save_slots(actor=self.owner, edits=self.edits(slots, [19, 20, 21, 18]))
        with patch(
            "core.recurring.AuditEvent.objects.create",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.generate(changed, update_existing=True)
        self.assertEqual(
            list(Session.objects.order_by("pk").values_list("starts_at", flat=True)), original
        )

    def test_closed_dated_public_visible_but_closed_weekly_default_hidden(self):
        slot = self.slots()[0]
        self.generate([slot])
        row = Session.objects.get(source_slot=slot)
        row.closed = True
        row.save()
        self.assertEqual(availability(row)["label"], "Not Available")
        self.assertFalse(availability(row)["hidden"])
        save_slot(
            actor=self.owner,
            pk=slot.pk,
            revision=slot.revision,
            data={f: getattr(slot, f) for f in FIELDS} | {"active": False},
        )
        self.assertTrue(availability(row)["hidden"])

    def test_staff_cannot_open_or_submit_batch_editor_or_session_management(self):
        self.client.force_login(self.staff)
        for path in ("/staff/scheduling/weekly/edit-all/", "/staff/scheduling/new/"):
            self.assertEqual(self.client.get(path).status_code, 403)
            self.assertEqual(self.client.post(path, {}).status_code, 403)

    def test_generation_has_explicit_unchanged_and_existing_conflict_links(self):
        slots = self.slots()
        self.generate(slots)
        results = self.generate(slots, update_existing=True)
        self.assertTrue(all(r["outcome"] == "Unchanged" for r in results))
        slot = slots[0]
        save_slot(
            actor=self.owner,
            pk=slot.pk,
            revision=slot.revision,
            data={f: getattr(slot, f) for f in FIELDS} | {"active": False},
        )
        replacement = save_slot(
            actor=self.owner,
            data={f: getattr(slot, f) for f in FIELDS} | {"label": "Replacement", "active": True},
        )
        result = self.generate([replacement])[0]
        self.assertEqual(result["display_outcome"], "Not generated")
        self.assertEqual(result["conflicts"][0]["id"], Session.objects.get(source_slot=slot).pk)

    def test_weekly_screen_uses_reservation_labels_and_conflicts_include_effective_closure(self):
        slots = self.slots()
        self.generate(slots)
        slot = slots[0]
        save_slot(
            actor=self.owner,
            pk=slot.pk,
            revision=slot.revision,
            data={f: getattr(slot, f) for f in FIELDS} | {"active": False},
        )
        replacement = save_slot(
            actor=self.owner,
            data={f: getattr(slot, f) for f in FIELDS} | {"label": "Replacement", "active": True},
        )
        result = self.generate([replacement])[0]
        self.assertTrue(result["conflicts"][0]["closed"])
        self.assertEqual(result["conflicts"][0]["end_time"], "06:45 PM")
        verified_owner_login(self.client, self.owner)
        response = self.client.get("/staff/scheduling/weekly/")
        self.assertContains(response, "Open for reservation")
        self.assertContains(response, "Closed for reservation")

    def test_batch_editor_posts_all_defaults_and_saves_final_arrangement(self):
        custom = self.slots()
        verified_owner_login(self.client, self.owner)
        response = self.client.get("/staff/scheduling/weekly/edit-all/")
        forms = response.context["formset"].initial
        payload = {
            "form-TOTAL_FORMS": str(len(forms)),
            "form-INITIAL_FORMS": str(len(forms)),
            "form-MAX_NUM_FORMS": "500",
            "form-MIN_NUM_FORMS": "0",
        }
        changes = {row.pk: hour for row, hour in zip(custom, [19, 20, 21, 18])}
        for i, initial in enumerate(forms):
            for key, value in initial.items():
                if key in {"starts_at", "ends_at"}:
                    hour = changes.get(initial["slot_id"])
                    value = (time(hour, 45 if key == "ends_at" else 0) if hour else value).strftime(
                        "%H:%M"
                    )
                payload[f"form-{i}-{key}"] = value
        response = self.client.post("/staff/scheduling/weekly/edit-all/", payload)
        self.assertEqual(
            response.status_code,
            302,
            response.context["formset"].errors if response.status_code == 200 else "",
        )
        self.assertEqual(
            [WeeklySlot.objects.get(pk=row.pk).starts_at.hour for row in custom], [19, 20, 21, 18]
        )


@override_settings(STORAGES=STORAGES)
class StaffBatchTests(TestCase):
    setUp = scheduling_tests.SchedulingTests.setUp
    reserve = scheduling_tests.SchedulingTests.reserve
    create = scheduling_tests.SchedulingTests.create

    def test_today_has_empty_sessions_phone_email_search_and_no_session_management(self):
        session = self.create()
        self.client.force_login(self.staff)
        response = self.client.get("/staff/today/")
        self.assertEqual(len(response.context["session_overview"]), 1)
        self.assertContains(response, f'value="{session.pk}"')
        self.assertContains(response, f"/staff/bookings/new/?session={session.pk}")
        self.assertNotContains(response, "/staff/scheduling/new/")
        self.reserve(session)
        for query in ("1" + self.customer.phone, self.customer.email):
            response = self.client.get("/staff/today/", {"q": query})
            self.assertEqual(len(response.context["bookings"]), 1)

    def test_empty_session_filter_keeps_its_zero_totals_visible(self):
        session = self.create()
        self.client.force_login(self.staff)
        response = self.client.get("/staff/today/", {"session": session.pk})
        self.assertEqual(len(response.context["bookings"]), 0)
        self.assertEqual(len(response.context["session_overview"]), 1)
        self.assertEqual(response.context["session_overview"][0]["bookings"], 0)
        self.assertContains(response, "Selected session totals")

    def test_today_does_not_offer_add_booking_for_closed_session(self):
        session = self.create(closed=True)
        self.client.force_login(self.staff)
        response = self.client.get("/staff/today/")
        self.assertFalse(response.context["session_overview"][0]["bookable"])
        self.assertNotContains(response, f"/staff/bookings/new/?session={session.pk}")
        self.assertContains(response, "Closed for reservation")

    def test_email_digits_do_not_match_unrelated_phone_numbers(self):
        session = self.create()
        Customer.objects.filter(pk=self.customer.pk).update(email="family2@example.invalid")
        other = Customer.objects.create(
            last_name="Unrelated", phone="2025550188", email="other@example.invalid"
        )
        for customer in (self.customer, other):
            Booking.objects.create(customer=customer, session=session, children=1, adults=1)
        self.client.force_login(self.staff)
        response = self.client.get("/staff/bookings/", {"q": "family2@example.invalid"})
        self.assertEqual(
            [booking.customer_id for booking in response.context["bookings"]], [self.customer.pk]
        )
        response = self.client.get("/staff/customers/", {"q": "family2@example.invalid"})
        self.assertEqual(
            [customer.pk for customer in response.context["customers"]], [self.customer.pk]
        )

    def test_date_range_optional_clock_filter_and_combined_sort(self):
        first = self.create()
        second = self.create(
            starts_at=first.starts_at + timedelta(days=1), ends_at=first.ends_at + timedelta(days=1)
        )
        late = self.create(
            starts_at=first.starts_at + timedelta(hours=4),
            ends_at=first.ends_at + timedelta(hours=4),
        )
        for slot, count in ((first, 1), (second, 3), (late, 2)):
            Booking.objects.create(customer=self.customer, session=slot, children=count, adults=1)
        self.client.force_login(self.staff)
        params = {
            "start": NOW.date().isoformat(),
            "end": (NOW.date() + timedelta(days=1)).isoformat(),
            "q": self.customer.email,
            "sort": "-children",
        }
        response = self.client.get("/staff/bookings/", params)
        self.assertEqual([b.children for b in response.context["bookings"]], [3, 2, 1])
        response = self.client.get("/staff/bookings/", params | {"session": "11:00"})
        self.assertEqual([b.children for b in response.context["bookings"]], [3, 1])
        response = self.client.get("/staff/bookings/", params | {"start": "not-a-date"})
        self.assertEqual(len(response.context["bookings"]), 0)
        self.assertContains(response, "Enter a valid date")

    def test_unified_edit_moves_reprices_play_type_and_keeps_original_quote(self):
        source = self.create()
        target = self.create(
            starts_at=source.starts_at + timedelta(hours=3),
            ends_at=source.ends_at + timedelta(hours=3),
        )
        booking = self.reserve(source)
        original = booking.quotes.get()
        changed = edit_test_booking(
            actor=self.staff,
            booking_id=booking.pk,
            version=1,
            session=target,
            children=2,
            adults=0,
            babies=0,
            socks=0,
            expected_method="cash",
            supervised=True,
        )
        self.assertEqual(changed.session_id, target.pk)
        self.assertTrue(changed.supervised)
        self.assertEqual(changed.quotes.first().snapshot["subtotal"], "37.98")
        self.assertEqual(changed.quotes.first().policy_id, original.policy_id)
        original.refresh_from_db()
        self.assertEqual(original.revision, 1)
        before = (changed.session_id, changed.supervised, changed.edit_version)
        with self.assertRaises(ValidationError):
            edit_test_booking(
                actor=self.staff,
                booking_id=booking.pk,
                version=2,
                session=source,
                children=4,
                adults=0,
                babies=0,
                socks=0,
                expected_method="cash",
                supervised=True,
            )
        changed.refresh_from_db()
        self.assertEqual((changed.session_id, changed.supervised, changed.edit_version), before)

    def test_booking_history_retains_original_clock_after_session_record_changes(self):
        source = self.create()
        target = self.create(
            starts_at=source.starts_at + timedelta(hours=3),
            ends_at=source.ends_at + timedelta(hours=3),
        )
        booking = self.reserve(source)
        edit_test_booking(
            actor=self.staff,
            booking_id=booking.pk,
            version=1,
            session=target,
            children=1,
            adults=1,
            babies=0,
            socks=0,
            expected_method="card",
        )
        self.assertEqual(booking.quotes.count(), 1)
        Session.objects.filter(pk=source.pk).update(
            starts_at=source.starts_at + timedelta(minutes=15)
        )
        self.client.force_login(self.staff)
        response = self.client.get(f"/staff/bookings/{booking.pk}/")
        self.assertContains(response, "11:00 AM")
        self.assertNotContains(response, "11:15 AM")

    def test_amount_change_requires_explicit_method_review_in_form(self):
        booking = self.reserve(self.create())
        args = dict(
            session=booking.session_id,
            children=2,
            adults=1,
            babies=0,
            socks=0,
            expected_method="card",
            version=1,
        )
        form = TestBookingForm(args, booking=booking)
        self.assertFalse(form.is_valid())
        self.assertIn("payment_reviewed", form.errors)
        form = TestBookingForm(args | {"payment_reviewed": "keep"}, booking=booking)
        self.assertTrue(form.is_valid(), form.errors)

    def test_searchable_customer_picker_normalizes_phone_and_requires_permission(self):
        self.client.force_login(self.staff)
        result = self.client.get("/staff/customers/search/", {"q": "1" + self.customer.phone})
        self.assertEqual(result.json()["results"][0]["id"], self.customer.pk)
        self.client.logout()
        self.assertEqual(
            self.client.get("/staff/customers/search/", {"q": "Test"}).status_code, 302
        )

    def test_optional_email_and_case_insensitive_current_email_uniqueness(self):
        for number in ("2025550181", "2025550182"):
            customer = create_customer(
                actor=self.staff, last_name="No email", phone=number, email=""
            )
            self.assertEqual(customer.email, "")
        with self.assertRaises(ValidationError):
            create_customer(
                actor=self.staff,
                last_name="Duplicate",
                phone="2025550183",
                email=self.customer.email.upper(),
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Customer.objects.create(
                last_name="SQL duplicate", phone="2025550184", email=self.customer.email.upper()
            )

    def test_staff_can_reuse_historical_email_with_warning(self):
        previous = self.customer.email
        update_customer(
            actor=self.staff,
            customer_id=self.customer.pk,
            revision=1,
            last_name="Test",
            phone=self.customer.phone,
            email="new@example.invalid",
        )
        self.client.force_login(self.staff)
        response = self.client.post(
            "/staff/customers/new/",
            {"last_name": "Other", "phone": "2025550183", "email": previous},
            follow=True,
        )
        self.assertContains(response, "appears in another customer")
        self.assertTrue(Customer.objects.filter(phone="2025550183").exists())

    def test_owner_membership_short_term_is_explicit_and_staff_cannot_forge_it(self):
        args = dict(
            customer=self.customer,
            places=1,
            months=1,
            starts_on=NOW.date(),
            expected_method="cash",
            creation_key=uuid.uuid4(),
        )
        for kind in ("subscription", "unlimited"):
            for billing in ("monthly", "prepaid"):
                with self.assertRaises(ValidationError):
                    create_draft(actor=self.owner, kind=kind, billing=billing, **args)
                draft = create_draft(
                    actor=self.owner,
                    kind=kind,
                    billing=billing,
                    **(args | {"creation_key": uuid.uuid4()}),
                    minimum_override=True,
                )
                self.assertTrue(draft.snapshot["owner_minimum_override"])
        with self.assertRaises(PermissionDenied):
            create_draft(
                actor=self.staff,
                kind="subscription",
                billing="monthly",
                **args,
                minimum_override=True,
            )

    def test_cancellation_requires_confirmation_even_without_javascript(self):
        booking = self.reserve(self.create())
        self.client.force_login(self.staff)
        response = self.client.post(f"/staff/bookings/{booking.pk}/release/", {"version": 1})
        self.assertContains(response, "Are you sure you want to cancel this visit?")
        booking.refresh_from_db()
        self.assertFalse(booking.attendance)
        self.client.post(
            f"/staff/bookings/{booking.pk}/release/", {"version": 1, "confirm_cancel": "1"}
        )
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "cancelled")


@override_settings(CUSTOMER_TEST_BOOKING=True, STORAGES=STORAGES)
class PublicBatchTests(TestCase):
    setUp = public_tests.PublicBookingTests.setUp
    begin = public_tests.PublicBookingTests.begin
    new_review = public_tests.PublicBookingTests.new_review
    confirm = public_tests.PublicBookingTests.confirm

    def test_returning_no_match_offers_previous_phone_before_new_customer(self):
        self.begin(visited="yes")
        response = self.client.get("/book/details/")
        self.assertContains(response, "No customer was found with 2025550191")
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "retry_phone")
        customer = Customer.objects.create(
            last_name="Other",
            phone="2025550183",
            previous_phone="2025550184",
            email="other@example.invalid",
        )
        self.client.post("/book/details/", {"phone": customer.previous_phone})
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "previous")
        self.client.post("/book/details/", {"confirm_phone": "yes"})
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "details")

    def test_duplicate_current_email_is_inline_validation_and_keeps_contact_form(self):
        customer = Customer.objects.create(
            last_name="Other", phone="2025550183", email="other@example.invalid"
        )
        self.begin()
        response = self.client.post(
            "/book/details/", {"last_name": "New", "email": customer.email.upper()}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists for another customer")
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "contact")
        self.assertFalse(Booking.objects.exists())

    def test_historical_email_allows_public_booking_and_adds_owner_only_notice(self):
        previous = Customer.objects.create(
            last_name="Other",
            phone="2025550183",
            previous_email="sample@example.invalid",
            email="other@example.invalid",
        )
        self.new_review()
        self.confirm()
        notice = OwnerNotice.objects.get()
        self.assertEqual(notice.details["previous_customer_ids"], [previous.pk])
        self.assertNotContains(self.client.get("/book/receipt/"), previous.last_name)
        from tests.test_customers import staff_user

        staff = staff_user()
        self.client.force_login(staff)
        self.assertNotContains(self.client.get("/staff/dashboard/"), "Email address reused")
        self.assertEqual(self.client.post(f"/staff/notices/{notice.pk}/review/").status_code, 403)
        owner = staff_user("owner", owner=True)
        verified_owner_login(self.client, owner)
        self.assertContains(self.client.get("/staff/dashboard/"), "Email address reused")
        self.assertEqual(self.client.post(f"/staff/notices/{notice.pk}/review/").status_code, 302)
        notice.refresh_from_db()
        self.assertIsNotNone(notice.reviewed_at)

    def test_csrf_rejection_keeps_protection_and_explains_recovery(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/book/details/", {"email": "other@example.invalid"})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Please refresh your form", status_code=403)
        self.assertFalse(Customer.objects.exists())

    def test_existing_customer_without_email_must_supply_it_before_public_booking(self):
        customer = Customer.objects.create(last_name="NoEmail", phone="2025550185", email="")
        self.begin(customer.phone, "yes")
        self.client.post("/book/details/", {"last_name": "NoEmail"})
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "email")
        self.client.post("/book/details/", {"email": "provided@example.invalid"})
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "details")
        self.client.post(
            "/book/details/",
            {
                "play_type": "open",
                "children": 1,
                "adults": 1,
                "babies": 0,
                "socks": 0,
                "expected_method": "cash",
                "referral_source": "",
            },
        )
        self.assertEqual(self.confirm().status_code, 302)
        customer.refresh_from_db()
        self.assertEqual(customer.email, "provided@example.invalid")
        self.assertEqual(Booking.objects.get().customer_id, customer.pk)


class DisplayRulesTests(SimpleTestCase):
    def test_approved_spelling_examples_and_pm_label(self):
        for name in ("Zarger", "Zharger", "Zorge"):
            self.assertTrue(similar_name("Zorger", name), name)
        self.assertTrue(similar_name("customer", "customir"))
        self.assertEqual(
            display_session_label("Standard play 2:40", time(14, 40)), "Standard play 2:40 PM"
        )
        self.assertEqual(display_session_label("Standard play 14:40"), "Standard play 2:40 PM")
        self.assertEqual(display_session_label("Standard play 2:40"), "Standard play 2:40")
