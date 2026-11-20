"""Explicit recovery collects only unpaid components and never replays unknown charges."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.models import FinancialLineAdjustment, FinancialPosting, PaymentOperation, PricingPolicy
from core.payments import remainders
from core.payments.checkout import summary
from core.payments.invoices import received
from core.payments.operations import execute
from core.waivers.services import set_paper
from tests import test_booking_checkout as fixtures


@override_settings(
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)
class RemainingPaymentTests(TestCase):
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

    def decline(self, operation):
        with patch("core.payments.operations.Gateway") as gateway:
            gateway.return_value.charge.return_value = {"status_code": "D"}
            execute(operation.pk)

    def test_partial_cash_is_not_charged_again_when_only_the_card_remainder_is_retried(self):
        PricingPolicy.objects.create(
            child_price=Decimal("25"), tax_rate=Decimal("0"), card_fee_rate=Decimal("0")
        )
        booking = self.booking()
        set_paper(
            actor=self.staff,
            booking_id=booking.pk,
            revision=booking.waiver_review.revision,
            signed=True,
        )
        checkout = self.act(
            booking, self.arrival_inputs(booking, children=3, method="split", split={"cash": "40"})
        )
        original = checkout.sale.operations.get(tender="card")
        self.decline(original)
        _, _, facts, digest, _ = remainders.preview(
            actor=self.staff, booking_id=booking.pk, method="card", context="arrival"
        )
        self.assertEqual(facts["amount"], "35.00")
        key = uuid.uuid4()
        result = remainders.confirm(
            actor=self.staff,
            booking_id=booking.pk,
            method="card",
            context="arrival",
            request_key=key,
            reviewed_hash=digest,
            confirmed=True,
        )
        remainders.confirm(
            actor=self.staff,
            booking_id=booking.pk,
            method="card",
            context="arrival",
            request_key=key,
            reviewed_hash=digest,
            confirmed=True,
        )
        retry = result.sale.operations.filter(tender="card").exclude(pk=original.pk).get()
        self.assertEqual(retry.amount, Decimal("35"))
        self.assertEqual(result.sale.operations.filter(tender="cash").count(), 1)
        with patch("core.payments.operations.Gateway") as gateway:
            gateway.return_value.charge.return_value = {"status_code": "A", "reference_number": 777}
            gateway.return_value.transaction.return_value = {
                "id": 777,
                "amount_details": {"amount": retry.amount},
                "transaction_details": {"type": "charge"},
                "status_details": {"status": "captured"},
                "custom_fields": {"custom1": str(retry.pk), "custom2": "monkeydo:sandbox"},
            }
            execute(retry.pk)
        self.assertEqual(received(result.sale), Decimal("75"))
        self.assertEqual(summary(booking)["status"], "Paid")
        original.refresh_from_db()
        self.assertIsNotNone(original.followup.resolved_at)

    def test_noncard_remainder_preview_does_not_adjust_invoice_and_final_removes_unused_fee(self):
        booking = self.booking()
        checkout = self.act(booking, self.arrival_inputs(booking))
        self.decline(checkout.sale.operations.get())
        _, _, facts, digest, _ = remainders.preview(
            actor=self.staff, booking_id=booking.pk, method="cash", context="arrival"
        )
        self.assertEqual(facts["amount"], "15.99")
        self.assertFalse(FinancialLineAdjustment.objects.exists())
        remainders.confirm(
            actor=self.staff,
            booking_id=booking.pk,
            method="cash",
            context="arrival",
            request_key=uuid.uuid4(),
            reviewed_hash=digest,
            confirmed=True,
        )
        self.assertEqual(FinancialLineAdjustment.objects.count(), 1)
        self.assertEqual(FinancialPosting.objects.get().fee, Decimal("0"))
        self.assertEqual(received(checkout.sale), Decimal("15.99"))
        self.assertEqual(summary(booking)["status"], "Paid")

    def test_unknown_or_queued_result_blocks_a_new_payment_before_any_new_post(self):
        booking = self.booking()
        self.act(booking, self.arrival_inputs(booking))
        with self.assertRaises(ValidationError):
            remainders.preview(actor=self.staff, booking_id=booking.pk, method="cash")
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertFalse(FinancialPosting.objects.exists())
