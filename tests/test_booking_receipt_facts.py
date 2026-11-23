"""Actual receipt dates and Zelle facts cannot be changed by review/replay."""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core.availability import NEW_YORK
from core.models import FinancialPosting, PaymentOperation
from core.payments.checkout import confirm, preview
from tests import test_booking_checkout as fixtures


@override_settings(
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)
class ReceiptFactsTests(TestCase):
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

    def test_zelle_requires_sender_and_actual_receipt_date_survives_as_a_date(self):
        booking = self.booking()
        values = self.arrival_inputs(booking, method="zelle")
        with self.assertRaises(ValidationError):
            preview(actor=self.staff, booking_id=booking.pk, kind="arrival", data=values)
        yesterday = timezone.localdate(timezone=NEW_YORK) - timedelta(days=1)
        from core.payments.zelle import record_receipt

        record_receipt(
            actor=self.staff,
            booking_id=booking.pk,
            request_key=uuid.uuid4(),
            value="15.99",
            received_on=yesterday,
            sender_name="Guardian bank account",
            verified=True,
        )
        result = self.act(booking, values)
        operation = result.sale.operations.get()
        self.assertEqual(operation.manual_received_on, yesterday)
        self.assertEqual(operation.amount, Decimal("15.99"))
        self.assertEqual(operation.zelle_application.receipt.sender, "Guardian bank account")
        self.assertIsNone(FinancialPosting.objects.get().occurred_at)
        with self.assertRaises(DatabaseError), transaction.atomic():
            PaymentOperation.objects.filter(pk=operation.pk).update(
                manual_received_on=yesterday - timedelta(days=1)
            )

    def test_cash_receipt_date_is_automatic_and_cannot_be_backdated_from_hidden_inputs(self):
        booking = self.booking()
        values = self.arrival_inputs(booking, method="cash")
        reviewed = preview(actor=self.staff, booking_id=booking.pk, kind="arrival", data=values)
        values["received_on"] = timezone.localdate(timezone=NEW_YORK) - timedelta(days=1)
        result = confirm(
            actor=self.staff,
            booking_id=booking.pk,
            kind="arrival",
            data=values,
            request_key=uuid.uuid4(),
            reviewed_hash=reviewed[-1],
            confirmed=True,
        )
        self.assertEqual(
            result.sale.operations.get().manual_received_on, timezone.localdate(timezone=NEW_YORK)
        )
        self.assertEqual(FinancialPosting.objects.count(), 1)
