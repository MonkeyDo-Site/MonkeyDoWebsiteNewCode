"""Only an explicit final review action can record attendance and money."""

import uuid

from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import BookingCheckout, FinancialPosting
from tests import test_booking_checkout as fixtures


@override_settings(
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)
class CheckoutViewTests(TestCase):
    setUp = fixtures.CheckoutTests.setUp
    create = fixtures.CheckoutTests.create
    flow = fixtures.CheckoutTests.flow
    card = fixtures.CheckoutTests.card
    save_card = fixtures.CheckoutTests.save_card
    gateway = fixtures.CheckoutTests.gateway
    ready = fixtures.CheckoutTests.ready
    booking = fixtures.CheckoutTests.booking

    def values(self, booking):
        return dict(
            request_key=str(uuid.uuid4()),
            version=booking.edit_version,
            children=booking.children,
            adults=booking.adults,
            babies=booking.babies,
            socks=booking.socks,
            waiver_confirmed="yes",
            method="cash",
        )

    def test_get_preview_and_final_confirmation_have_distinct_effects(self):
        booking = self.booking()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[booking.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        values = self.values(booking)
        response = self.client.post(url, values | {"preview": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm arrival and record cash")
        self.assertFalse(BookingCheckout.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())
        digest = response.context["form"]["reviewed_hash"].value()
        response = self.client.post(
            url, values | {"reviewed_hash": digest, "confirm_review": "1"}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paid")
        self.assertEqual(FinancialPosting.objects.count(), 1)
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "arrived")

    def test_no_waiver_preserves_inputs_and_never_persists_a_final_action_hidden_field(self):
        booking = self.booking()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[booking.pk])
        values = self.values(booking) | {
            "waiver_confirmed": "no",
            "confirm_review": "1",
            "reviewed_hash": "invalid",
        }
        response = self.client.post(url, values)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Return to waiver handling")
        self.assertEqual(response.context["form"]["children"].value(), str(booking.children))
        self.assertNotIn("confirm_review", response.context["form"].fields)
        self.assertFalse(FinancialPosting.objects.exists())
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "")

    def test_closure_requires_an_explicit_fee_choice_and_original_test_bookings_stay_separate(self):
        booking = self.booking()
        self.client.force_login(self.staff)
        url = reverse("booking_cancel", args=[booking.pk])
        values = {
            "request_key": str(uuid.uuid4()),
            "version": booking.edit_version,
            "send_email": "no",
        }
        response = self.client.post(url, values)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BookingCheckout.objects.exists())
        response = self.client.post(url, values | {"charge_fee": "no"})
        digest = response.context["form"]["reviewed_hash"].value()
        self.assertContains(response, "Confirm cancellation without a fee")
        response = self.client.post(
            url, values | {"charge_fee": "no", "reviewed_hash": digest, "confirm_review": "1"}
        )
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "cancelled")
        self.assertFalse(FinancialPosting.objects.exists())

    def test_card_balance_confirmation_does_not_treat_hidden_manual_date_as_provider_date(self):
        from core.payments.checkout import confirm, preview
        from core.payments.ledger import record_result

        booking = self.booking()
        values = dict(
            children=booking.children,
            adults=booking.adults,
            babies=booking.babies,
            socks=booking.socks,
            method="card",
            waiver_confirmed=True,
        )
        reviewed = preview(actor=self.staff, booking_id=booking.pk, kind="arrival", data=values)
        result = confirm(
            actor=self.staff,
            booking_id=booking.pk,
            kind="arrival",
            data=values,
            request_key=uuid.uuid4(),
            reviewed_hash=reviewed[-1],
            confirmed=True,
        )
        operation = result.sale.operations.get()
        record_result(
            operation_id=operation.pk, state="declined", source="provider", code="synthetic_decline"
        )
        self.client.force_login(self.staff)
        url = reverse("booking_payment", args=[booking.pk])
        posted = {"request_key": str(uuid.uuid4()), "method": "card", "context": "arrival"}
        response = self.client.post(url, posted)
        self.assertEqual(response.status_code, 200)
        digest = response.context["form"]["reviewed_hash"].value()
        response = self.client.post(url, posted | {"reviewed_hash": digest, "confirm_review": "1"})
        self.assertEqual(response.status_code, 302)
        next_operation = result.sale.operations.exclude(pk=operation.pk).get()
        self.assertEqual(next_operation.state, "ready")
        self.assertIsNone(next_operation.manual_received_on)
