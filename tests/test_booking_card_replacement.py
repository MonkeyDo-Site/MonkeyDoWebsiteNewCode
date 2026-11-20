"""A reviewed replacement changes only this obligation and explicit future-use choice."""

import uuid
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.models import PaymentMethod
from core.payments.ledger import full_allocation, request_operation
from core.payments.setup import exchange, replace_booking_card
from tests import test_booking_checkout as fixtures


@override_settings(
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)
class CardReplacementTests(TestCase):
    setUp = fixtures.CheckoutTests.setUp
    create = fixtures.CheckoutTests.create
    flow = fixtures.CheckoutTests.flow
    card = fixtures.CheckoutTests.card
    save_card = fixtures.CheckoutTests.save_card
    gateway = fixtures.CheckoutTests.gateway
    ready = fixtures.CheckoutTests.ready
    booking = fixtures.CheckoutTests.booking
    arrival_inputs = fixtures.CheckoutTests.arrival_inputs
    act = fixtures.CheckoutTests.act

    def replacement(self, booking, retain=False):
        flow = self.flow()
        flow.update(
            stage="review",
            staff_actor=self.staff.pk,
            staff_booking=booking.pk,
            staff_booking_version=booking.edit_version,
            staff_action="replace",
            session_id=booking.session_id,
            details={
                name: getattr(booking, name)
                for name in (
                    "children",
                    "adults",
                    "babies",
                    "socks",
                    "supervised",
                    "expected_method",
                )
            },
        )
        with patch("core.payments.setup.Gateway") as gateway:
            gateway.return_value.create_customer.return_value = {"id": 12}
            gateway.return_value.save_card.return_value = {"id": 124}
            gateway.return_value.method.return_value = self.card() | {"id": 124, "last4": "5678"}
            saved = exchange(
                actor=self.staff,
                flow=flow,
                request_key=uuid.uuid4(),
                nonce="nonce-NewCard",
                expiry_month=12,
                expiry_year=2035,
                retain=retain,
                payment_accepted=True,
                cancellation_accepted=True,
            )
            gateway.return_value.charge.assert_not_called()
        flow["payment_consent"] = str(saved.consent_id)
        return flow

    def test_booking_only_replacement_preserves_previously_saved_future_card(self):
        booking = self.booking()
        old = booking.card_agreement.method
        old.reusable = True
        old.save(update_fields=["reusable"])
        flow = self.replacement(booking)
        result = replace_booking_card(actor=self.staff, flow=flow, booking_id=booking.pk)
        old.refresh_from_db()
        self.assertEqual(result.method.last_four, "5678")
        self.assertFalse(result.method.reusable)
        self.assertTrue(old.reusable)
        self.assertEqual(old.state, "active")

    def test_future_replacement_retires_previous_future_choice_and_does_not_charge(self):
        booking = self.booking()
        old = booking.card_agreement.method
        old.reusable = True
        old.save(update_fields=["reusable"])
        flow = self.replacement(booking, retain=True)
        result = replace_booking_card(actor=self.staff, flow=flow, booking_id=booking.pk)
        old.refresh_from_db()
        self.assertFalse(old.reusable)
        self.assertTrue(result.method.reusable)
        self.assertEqual(PaymentMethod.objects.filter(reusable=True, state="active").count(), 1)

    def test_pending_charge_blocks_replacement_and_stale_source_cannot_charge(self):
        booking = self.booking()
        old = booking.card_agreement.method
        flow = self.replacement(booking)
        replace_booking_card(actor=self.staff, flow=flow, booking_id=booking.pk)
        result = self.act(booking, self.arrival_inputs(booking))
        with self.assertRaises(ValidationError):
            request_operation(
                actor=self.staff,
                sale_id=result.sale_id,
                request_key=uuid.uuid4(),
                tender="card",
                allocation=full_allocation(result.sale),
                method_id=old.pk,
            )
        with self.assertRaises(ValidationError):
            replace_booking_card(actor=self.staff, flow=flow, booking_id=booking.pk)
