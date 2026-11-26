"""Third owner batch: matching, history filters, custom blocks and public recovery."""

import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from unittest import skipUnless

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings

from core.availability import availability
from core.booking_management import release_test_booking
from core.models import Booking, Customer, Session, SessionReservationBlock
from core.name_matching import similar_name
from core.recurring import generate_sessions, save_slot
from core.schedule_coverage import describe_coverage
from core.scheduling import save_date, save_session
from core.session_blocks import SessionConflict, reopen_custom
from tests.helpers import verified_owner_login
from tests.test_owner_accounts import STORAGES
from tests.test_public_booking import PublicBookingTests
from tests.test_scheduling import NOW, SchedulingTests


@override_settings(STORAGES=STORAGES)
class SchedulingThirdBatchTests(TestCase):
    setUp = SchedulingTests.setUp
    create = SchedulingTests.create
    reserve = SchedulingTests.reserve

    def custom(self, **kwargs):
        return save_session(
            actor=self.owner,
            data={
                **self.data,
                "custom_blocking": True,
                "starts_at": NOW + timedelta(minutes=1),
                "ends_at": NOW + timedelta(hours=4),
                **kwargs,
            },
        )

    def test_backend_date_hides_current_and_future_sessions_but_allows_staff(self):
        slot = self.create()
        save_date(
            actor=self.owner,
            day=NOW.date(),
            closed=False,
            backend_only=True,
            private_reason="",
            chol_hamoed=False,
            revision=0,
        )
        self.assertTrue(availability(slot)["hidden"])
        self.assertTrue(self.reserve(slot).pk)
        later = self.create(starts_at=NOW + timedelta(hours=5), ends_at=NOW + timedelta(hours=6))
        self.assertTrue(availability(later)["hidden"])
        save_date(
            actor=self.owner,
            day=NOW.date(),
            closed=False,
            backend_only=False,
            private_reason="",
            chol_hamoed=False,
            revision=1,
        )
        self.assertTrue(availability(slot)["available"])

    def test_custom_blocks_preserve_original_session_and_prevent_reservations(self):
        slot = self.create()
        original = slot.starts_at
        custom = self.custom()
        slot.refresh_from_db()
        self.assertEqual(slot.starts_at, original)
        self.assertEqual(availability(slot)["label"], "Not Available")
        with self.assertRaises(ValidationError):
            self.reserve(slot)
        self.assertTrue(self.reserve(custom).pk)

    def test_custom_reports_exact_existing_booking_and_rolls_back(self):
        slot = self.create()
        booking = self.reserve(slot)
        with self.assertRaises(SessionConflict) as caught:
            self.custom()
        self.assertEqual([row.pk for row in caught.exception.bookings], [booking.pk])
        self.assertFalse(SessionReservationBlock.objects.exists())
        self.assertEqual(Session.objects.count(), 1)

    def test_reopen_preserves_independent_manual_closure(self):
        slot = self.create(closed=True)
        custom = self.custom()
        reopen_custom(self.owner, custom.pk, custom.revision)
        slot.refresh_from_db()
        self.assertTrue(slot.closed)
        self.assertFalse(availability(slot)["available"])
        self.assertFalse(custom.caused_blocks.filter(active=True).exists())

    def test_owner_booking_closure_atomic_and_explicit_reopen(self):
        slot = self.create()
        booking = self.reserve(slot, actor=self.owner, close_session=True)
        self.assertFalse(availability(slot)["available"])
        release_test_booking(
            actor=self.owner, booking_id=booking.pk, version=1, reopen_affected_sessions=True
        )
        self.assertTrue(availability(slot)["available"])

    def test_ordinary_cancel_does_not_automatically_reopen(self):
        slot = self.create()
        booking = self.reserve(slot, actor=self.owner, close_session=True)
        release_test_booking(actor=self.owner, booking_id=booking.pk, version=1)
        self.assertFalse(availability(slot)["available"])

    def test_staff_cannot_close_or_reopen_session_through_booking(self):
        slot = self.create()
        with self.assertRaises(PermissionDenied):
            self.reserve(slot, close_session=True)
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(SessionReservationBlock.objects.exists())

    def test_invalid_booking_does_not_leave_session_closed(self):
        slot = self.create()
        with self.assertRaises(ValidationError):
            self.reserve(slot, actor=self.owner, close_session=True, children=50)
        self.assertTrue(availability(slot)["available"])

    def test_custom_duplicate_start_can_coexist_without_rewriting_standard(self):
        slot = self.create()
        custom = self.custom(starts_at=slot.starts_at)
        self.assertNotEqual(custom.pk, slot.pk)
        self.assertEqual(custom.starts_at, slot.starts_at)
        self.assertEqual(Session.objects.count(), 2)

    def test_stale_custom_preview_cannot_block_new_unreviewed_session(self):
        slot = self.create()
        with self.assertRaisesMessage(ValidationError, "affected sessions changed"):
            save_session(
                actor=self.owner, data=self.data | {"custom_blocking": True}, expected_conflicts=[]
            )
        self.assertEqual(Session.objects.count(), 1)
        self.assertTrue(availability(slot)["available"])

    def test_reopen_custom_refuses_existing_active_booking(self):
        custom = self.custom()
        self.reserve(custom)
        with self.assertRaises(ValidationError):
            reopen_custom(self.owner, custom.pk, custom.revision)

    def test_current_schedule_coverage_stops_at_different_timing(self):
        slot = save_slot(
            actor=self.owner,
            data=dict(
                label="Test",
                weekdays=list(range(7)),
                starts_at=time(18),
                ends_at=time(19),
                active=True,
                public=True,
                play_mode="accompanied",
                child_capacity=35,
                total_capacity=50,
                supervised_capacity=0,
            ),
        )
        generate_sessions(
            actor=self.owner,
            slot_ids=[slot.pk],
            from_day=NOW.date(),
            through_day=NOW.date() + timedelta(days=5),
        )
        slot = save_slot(
            actor=self.owner,
            pk=slot.pk,
            revision=slot.revision,
            data={
                key: getattr(slot, key)
                for key in (
                    "label",
                    "weekdays",
                    "starts_at",
                    "ends_at",
                    "active",
                    "public",
                    "play_mode",
                    "child_capacity",
                    "total_capacity",
                    "supervised_capacity",
                )
            }
            | {"starts_at": time(18, 15)},
        )
        generate_sessions(
            actor=self.owner,
            slot_ids=[slot.pk],
            from_day=NOW.date(),
            through_day=NOW.date() + timedelta(days=2),
            update_existing=True,
        )
        describe_coverage(slot)
        self.assertEqual(slot.current_until, NOW.date() + timedelta(days=2))
        self.assertEqual(slot.generated_until, NOW.date() + timedelta(days=5))
        self.assertEqual(len(slot.coverage_ranges), 2)
        self.assertIn("Earlier timing", slot.coverage_ranges[-1]["status"])

    def test_bookings_empty_dates_include_history_and_default_is_year(self):
        booking = self.reserve(self.create())
        past = Session.objects.create(
            starts_at=NOW - timedelta(days=50), ends_at=NOW - timedelta(days=50, minutes=-75)
        )
        old = Booking.objects.create(customer=self.customer, session=past, children=1, adults=1)
        verified_owner_login(self.client, self.owner)
        response = self.client.get("/staff/bookings/")
        self.assertContains(response, f"/staff/bookings/{booking.pk}/")
        self.assertNotContains(response, f"/staff/bookings/{old.pk}/")
        response = self.client.get(
            "/staff/bookings/", {"start": "", "end": "", "q": self.customer.last_name}
        )
        self.assertContains(response, f"/staff/bookings/{old.pk}/")
        self.assertContains(response, f"/staff/bookings/{booking.pk}/")

    def test_customer_type_filter_and_school(self):
        school = Customer.objects.create(
            last_name="School Test", phone="2025550190", customer_type="school"
        )
        verified_owner_login(self.client, self.owner)
        response = self.client.get("/staff/customers/", {"type": "school"})
        self.assertContains(response, school.last_name)
        self.assertNotContains(response, f"/staff/customers/{self.customer.pk}/")


@override_settings(CUSTOMER_TEST_BOOKING=True, STORAGES=STORAGES)
class PublicThirdBatchTests(TestCase):
    setUp = PublicBookingTests.setUp
    begin = PublicBookingTests.begin
    new_review = PublicBookingTests.new_review
    confirm = PublicBookingTests.confirm

    def test_word_and_partial_typo_examples(self):
        for query, stored in [
            ("Brawn", "Braun Customer"),
            ("bnot", "bnos miriam"),
            ("Gree", "Greenfeld"),
            ("Greenfeld", "Greenfield"),
        ]:
            self.assertTrue(similar_name(query, stored))
        for query in ["", "x", "zzzz", "Braun Unrelated"]:
            self.assertFalse(similar_name(query, "Braun Customer"))

    def test_email_recovery_requires_two_matching_pieces_and_preserves_phone(self):
        c = Customer.objects.create(
            last_name="Braun Customer", phone="2025550100", email="braun@example.invalid"
        )
        self.begin(c.phone, "yes")
        self.client.post("/book/details/", {"last_name": "Unrelated"})
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "email_lookup")
        response = self.client.post("/book/details/", {"email": "wrong@example.invalid"})
        self.assertNotContains(response, c.last_name)
        response = self.client.post("/book/details/", {"email": c.email.upper()})
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get("/book/details/"), c.last_name)
        self.client.post("/book/details/", {})
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "details")
        self.assertContains(
            self.client.get("/book/details/"), "That email address matches our records"
        )
        c.refresh_from_db()
        self.assertEqual(c.phone, "2025550100")
        self.assertFalse(Booking.objects.exists())

    def test_unmatched_phone_email_recovery_does_not_change_customer(self):
        c = Customer.objects.create(
            last_name="Known", phone="2025550100", email="known@example.invalid"
        )
        self.begin("5145550199", "no")
        # A name already entered on the contact form can be reused; it is never asked again.
        self.client.post("/book/details/", {"last_name": "Kno", "email": c.email})
        self.client.post("/book/recover/")
        self.client.post("/book/details/", {"email": c.email})
        self.client.post("/book/details/", {})
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "details")
        c.refresh_from_db()
        self.assertEqual(c.phone, "2025550100")

    def test_email_recovery_uses_phone_without_repeating_name(self):
        c = Customer.objects.create(
            last_name="Known", phone="2025550100", email="known@example.invalid"
        )
        self.begin(c.phone, "yes")
        response = self.client.post("/book/details/", {"last_name": "Different"}, follow=True)
        self.assertNotContains(response, 'name="last_name"')
        self.assertContains(
            response, "We couldn't match the name ‘Different’ with phone number ‘202-555-0100’."
        )
        self.assertContains(
            response, "You can try finding your customer profile by entering your email address."
        )
        self.client.post("/book/details/", {"email": c.email})
        self.assertContains(self.client.get("/book/details/"), c.last_name)
        self.assertIn("proof", self.client.session["customer_test_booking"])

    def test_email_for_another_profile_cannot_override_a_matched_phone(self):
        current = Customer.objects.create(
            last_name="Current", phone="2025550100", email="current@example.invalid"
        )
        other = Customer.objects.create(
            last_name="Other", phone="2025550101", email="other@example.invalid"
        )
        self.begin(current.phone, "yes")
        self.client.post("/book/details/", {"last_name": other.last_name})
        response = self.client.post("/book/details/", {"email": other.email}, follow=True)
        self.assertNotContains(response, "Is this your family?")
        self.assertNotContains(response, other.phone)
        self.assertNotIn("candidate_name", self.client.session["customer_test_booking"])
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "conflict_name")

    def test_email_alone_with_unknown_phone_does_not_reveal_profile(self):
        c = Customer.objects.create(
            last_name="Known", phone="2025550100", email="known@example.invalid"
        )
        self.begin("5145550199", "yes")
        self.client.get("/book/recover/")
        response = self.client.post(
            "/book/details/", {"email": c.email, "last_name": c.last_name}, follow=True
        )
        self.assertNotContains(response, "Is this your family?")
        self.assertNotIn("candidate_name", self.client.session["customer_test_booking"])
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "recovered_name")

    def test_email_from_history_cannot_identify_customer(self):
        c = Customer.objects.create(
            last_name="Known",
            phone="2025550100",
            email="new@example.invalid",
            previous_email="old@example.invalid",
        )
        self.begin("5145550199", "yes")
        self.client.post("/book/recover/")
        response = self.client.post(
            "/book/details/", {"last_name": "Known", "email": c.previous_email}
        )
        self.assertEqual(self.client.session["customer_test_booking"]["stage"], "email_lookup")
        self.assertNotContains(response, c.phone)
        self.assertNotContains(response, "Is this your family?")

    def test_live_quote_is_read_only_pretax_and_final_quote_retains_tax(self):
        self.begin()
        self.client.post(
            "/book/details/", {"last_name": "Example", "email": "example@example.invalid"}
        )
        original = copy.deepcopy(self.client.session["customer_test_booking"])
        data = dict(
            play_type="open", children=2, adults=1, babies=0, socks=1, expected_method="card"
        )
        response = self.client.post("/book/estimate/", data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Total before applicable taxes", response.json()["html"])
        self.assertNotIn("Sales tax", response.json()["html"])
        self.assertNotIn("Credit-card processing fee", response.json()["html"])
        self.assertIn("$31.99", response.json()["html"])
        cash_response = self.client.post("/book/estimate/", data | {"expected_method": "cash"})
        self.assertEqual(cash_response.json()["html"], response.json()["html"])
        self.assertFalse(Booking.objects.exists())
        self.assertFalse(Customer.objects.exists())
        self.assertEqual(self.client.session["customer_test_booking"], original)
        self.client.post("/book/details/", data)
        final = self.client.get("/book/details/")
        self.assertContains(final, "Sales tax")
        self.assertContains(final, "Credit-card processing fee")
        self.assertContains(final, "$0.96")

    def test_new_customer_notice_does_not_claim_early_persistence(self):
        self.begin("5145550199", "yes")
        self.client.post("/book/details/", {"continue_new": "1"})
        self.client.post(
            "/book/details/", {"last_name": "Example", "email": "example@example.invalid"}
        )
        response = self.client.get("/book/details/")
        self.assertContains(response, "Your details are ready")
        self.assertNotContains(response, "No customer was found")
        self.assertFalse(Customer.objects.exists())


@override_settings(STORAGES=STORAGES)
@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL transaction locks")
class CustomSessionRaceTests(TransactionTestCase):
    setUp = SchedulingTests.setUp
    create = SchedulingTests.create
    reserve = SchedulingTests.reserve

    def test_custom_session_racing_a_booking_never_accepts_both(self):
        slot = self.create()

        def run(custom):
            close_old_connections()
            try:
                if custom:
                    save_session(
                        actor=self.owner,
                        data=self.data
                        | {
                            "custom_blocking": True,
                            "starts_at": NOW + timedelta(minutes=1),
                            "ends_at": NOW + timedelta(hours=4),
                        },
                    )
                else:
                    self.reserve(slot)
                return True
            except ValidationError:
                return False
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, [True, False]))
        self.assertEqual(sum(results), 1)
        if results[0]:
            self.assertTrue(
                SessionReservationBlock.objects.filter(session=slot, active=True).exists()
            )
            self.assertFalse(Booking.objects.exists())
        else:
            self.assertEqual(Booking.objects.count(), 1)
            self.assertFalse(Session.objects.filter(custom_blocking=True).exists())
