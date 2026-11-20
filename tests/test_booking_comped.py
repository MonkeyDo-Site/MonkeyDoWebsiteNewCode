"""Owner-only complimentary bookings retain waiver requirements and skip card/payment."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import FinancialPosting, PaymentMethod
from core.payments.comped import set_comped
from core.payments.staff_setup import session_key
from tests import test_staff_booking_setup as fixtures
from tests.test_owner_accounts import STORAGES


@override_settings(
    STORAGES=STORAGES,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
)
class ComplimentaryTests(TestCase):
    setUp = fixtures.StaffSetupTests.setUp
    create = fixtures.StaffSetupTests.create
    booking = fixtures.StaffSetupTests.booking

    def test_owner_comped_booking_can_be_confirmed_without_any_card_and_still_needs_waiver(self):
        booking = self.booking()
        set_comped(
            actor=self.owner, booking_id=booking.pk, version=booking.edit_version, comped=True
        )
        booking.refresh_from_db()
        self.assertEqual(booking.quotes.first().snapshot["total"], "0.00")
        self.client.force_login(self.staff)
        url = reverse("staff_booking_setup", args=[booking.pk])
        response = self.client.get(url)
        self.assertContains(response, "No card is required")
        self.assertNotContains(response, "data-payment-setup")
        flow = self.client.session[session_key(booking.pk)]
        self.assertEqual(
            self.client.post(
                url, {"wizard_key": flow["key"], "waiver_type": "single", "confirm": "on"}
            ).status_code,
            302,
        )
        booking.refresh_from_db()
        self.assertFalse(booking.setup_pending)
        self.assertFalse(booking.waiver_review.coverage_confirmed)
        self.assertFalse(PaymentMethod.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertNotIn("Cancellation fees will apply", booking.messages.get().text_body)

    def test_staff_cannot_mark_a_booking_comped(self):
        booking = self.booking()
        with self.assertRaises(PermissionDenied):
            set_comped(actor=self.staff, booking_id=booking.pk, version=1, comped=True)
        self.assertFalse(booking.charge_state.comped if hasattr(booking, "charge_state") else False)

    def test_stale_comped_choice_is_rejected(self):
        booking = self.booking()
        with self.assertRaises(ValidationError):
            set_comped(actor=self.owner, booking_id=booking.pk, version=99, comped=True)
