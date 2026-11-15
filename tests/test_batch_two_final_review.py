"""Customer-owned referral data and the final owner-review refinements."""

import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.booking_forms import TestBookingForm
from core.customers import create_customer, update_customer
from core.models import AuditEvent, Booking, Customer
from tests import test_public_booking as public_tests
from tests import test_scheduling as scheduling_tests
from tests.test_owner_accounts import STORAGES


@override_settings(STORAGES=STORAGES)
class StaffFinalReviewTests(TestCase):
    setUp = scheduling_tests.SchedulingTests.setUp
    create = scheduling_tests.SchedulingTests.create
    reserve = scheduling_tests.SchedulingTests.reserve

    def test_customer_referral_edits_are_audited_without_rewriting_old_bookings(self):
        customer = create_customer(
            actor=self.staff,
            last_name="New family",
            phone="2025550175",
            email="new@example.invalid",
            referral_source=" A friend ",
        )
        booking = self.reserve(self.create(), referral_source="Earlier booking answer")
        customer = update_customer(
            actor=self.staff,
            customer_id=customer.pk,
            revision=customer.revision,
            last_name=customer.last_name,
            phone=customer.phone,
            email=customer.email,
            referral_source="School newsletter",
        )
        event = AuditEvent.objects.get(action="customer.updated", record_id=str(customer.pk))
        self.assertEqual(
            event.changes["referral_source"],
            {"before": "A friend", "after": "School newsletter"},
        )
        with self.assertRaises(ValidationError):
            update_customer(
                actor=self.staff,
                customer_id=customer.pk,
                revision=1,
                last_name=customer.last_name,
                phone=customer.phone,
                email=customer.email,
                referral_source="Stale edit",
            )
        booking.refresh_from_db()
        self.assertEqual(booking.referral_source, "Earlier booking answer")
        self.client.force_login(self.staff)
        self.assertContains(
            self.client.get(f"/staff/customers/{customer.pk}/"), "School newsletter"
        )
        response = self.client.get(f"/staff/customers/{customer.pk}/history/")
        self.assertContains(response, "How did you hear about MonkeyDo?")
        self.assertContains(response, "A friend")
        self.assertContains(response, "School newsletter")

    def test_staff_forms_keep_referral_on_customer_and_play_type_above_counts(self):
        booking = self.reserve(self.create(), referral_source="Preserved answer")
        self.client.force_login(self.staff)
        for path in ("/staff/bookings/new/", f"/staff/bookings/{booking.pk}/edit/"):
            response = self.client.get(path)
            fields = list(response.context["form"].fields)
            self.assertLess(fields.index("session"), fields.index("supervised"))
            self.assertLess(fields.index("supervised"), fields.index("children"))
            self.assertNotIn("referral_source", fields)
            self.assertNotContains(response, 'class="booking-progress"')
        response = self.client.get(f"/staff/customers/{self.customer.pk}/edit/")
        self.assertIn("referral_source", response.context["form"].fields)
        response = self.client.get(f"/staff/bookings/{booking.pk}/")
        self.assertNotContains(response, "Preserved answer")
        visible_details = response.content.decode().split("<summary>Change history</summary>")[0]
        self.assertNotIn("How did you hear about MonkeyDo?", visible_details)
        booking.refresh_from_db()
        self.assertEqual(booking.referral_source, "Preserved answer")
        # Forged booking fields cannot change the customer or its historical booking answer.
        form = TestBookingForm(
            {
                "session": booking.session_id,
                "version": booking.edit_version,
                "children": 1,
                "adults": 1,
                "babies": 0,
                "socks": 0,
                "expected_method": "cash",
                "referral_source": "Injected booking answer",
            },
            booking=booking,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("referral_source", form.cleaned_data)

    def test_all_sessions_overrides_prior_selections_and_summary_lists_selected_times(self):
        first = self.create()
        second = self.create(
            starts_at=first.starts_at + timedelta(hours=3),
            ends_at=first.ends_at + timedelta(hours=3),
        )
        self.reserve(first)
        self.reserve(second)
        self.client.force_login(self.staff)
        for path, selection in (
            ("/staff/today/", str(first.pk)),
            ("/staff/bookings/", "11:00"),
        ):
            response = self.client.get(path, {"session": selection})
            self.assertEqual(len(response.context["bookings"]), 1)
            self.assertContains(response, "Sessions · 1 selected · 11:00 AM")
            response = self.client.get(path, {"session": selection, "all_sessions": "1"})
            self.assertEqual(len(response.context["bookings"]), 2)
            self.assertContains(response, "Sessions · All sessions")
            self.assertNotContains(response, "None selected includes all")


@override_settings(CUSTOMER_TEST_BOOKING=True, STORAGES=STORAGES)
class PublicFinalReviewTests(TestCase):
    setUp = public_tests.PublicBookingTests.setUp
    begin = public_tests.PublicBookingTests.begin
    confirm = public_tests.PublicBookingTests.confirm

    def details(self, **changes):
        return self.client.post(
            "/book/details/",
            {
                "play_type": "open",
                "children": 1,
                "adults": 1,
                "babies": 0,
                "socks": 0,
                "expected_method": "cash",
            }
            | changes,
        )

    def test_new_referral_is_collected_once_and_saved_only_with_successful_booking(self):
        self.begin()
        form = self.client.get("/book/details/").context["form"]
        self.assertEqual(form.fields["referral_source"].label, "How did you hear about MonkeyDo?")
        self.client.post(
            "/book/details/",
            {
                "last_name": "New family",
                "email": "new@example.invalid",
                "referral_source": "Friend",
            },
        )
        response = self.client.get("/book/details/")
        self.assertNotIn("referral_source", response.context["form"].fields)
        self.details(referral_source="Ignored injection")
        self.assertFalse(Customer.objects.exists())
        self.confirm()
        booking = Booking.objects.get()
        self.assertEqual(booking.customer.referral_source, "Friend")
        self.assertEqual(booking.referral_source, "")
        created = AuditEvent.objects.get(action="customer.public_test_created")
        self.assertEqual(created.changes["referral_source"], "Friend")
        self.confirm()
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Booking.objects.count(), 1)

    def test_returning_customer_keeps_referral_and_payment_screen_omits_verification_message(self):
        customer = Customer.objects.create(
            last_name="Existing",
            phone="2025550100",
            email="existing@example.invalid",
            referral_source="Original source",
        )
        self.begin(customer.phone, "yes")
        self.assertNotContains(self.client.get("/book/details/"), customer.email)
        self.client.post("/book/details/", {"last_name": "Existing"})
        response = self.client.get("/book/details/")
        self.assertContains(response, customer.email)
        self.assertContains(response, "That name matches our records")
        self.assertNotIn("referral_source", response.context["form"].fields)
        self.details(referral_source="Untrusted replacement")
        response = self.client.get("/book/details/")
        self.assertNotContains(response, "That name matches our records")
        self.assertContains(response, "Change your session details or your payment method")
        self.confirm()
        customer.refresh_from_db()
        self.assertEqual(customer.referral_source, "Original source")
        response = self.client.get("/book/receipt/")
        self.assertContains(response, "You're all set for your MonkeyDo adventure!")
        self.assertContains(response, "Book another play session")
        self.assertContains(response, "not a confirmed visit")
        self.assertEqual(Booking.objects.get().status_label, "Setup pending")

    def test_referral_profile_write_rolls_back_if_capacity_disappears(self):
        self.begin()
        self.client.post(
            "/book/details/",
            {"last_name": "New", "email": "new@example.invalid", "referral_source": "School"},
        )
        self.details()
        customer = Customer.objects.create(
            last_name="Other", phone="2025550100", email="other@example.invalid"
        )
        Booking.objects.create(
            customer=customer, session=self.slot, children=35, adults=1, creation_key=uuid.uuid4()
        )
        self.confirm()
        self.assertFalse(Customer.objects.filter(email="new@example.invalid").exists())
        self.assertFalse(AuditEvent.objects.filter(action="customer.public_test_created").exists())
