"""Completion-page session capability updates one profile and one booking confirmation."""

import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.booking_email import correct_email
from core.communications.services import claim
from core.models import Booking, Customer, MessageDelivery
from core.public_booking import submit_booking
from tests import test_completed_public_booking as fixtures


@override_settings(
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)
class CompletionEmailTests(TestCase):
    setUp = fixtures.CompletedPublicBookingTests.setUp
    create = fixtures.CompletedPublicBookingTests.create
    flow = fixtures.CompletedPublicBookingTests.flow
    card = fixtures.CompletedPublicBookingTests.card
    save_card = fixtures.CompletedPublicBookingTests.save_card
    gateway = fixtures.CompletedPublicBookingTests.gateway
    ready = fixtures.CompletedPublicBookingTests.ready

    def completed(self):
        flow = self.ready()
        booking = submit_booking(flow)
        flow.update(stage="done", booking_id=booking.pk)
        return flow, booking

    def test_change_preserves_history_and_only_one_current_confirmation_survives(self):
        flow, booking = self.completed()
        key = uuid.uuid4()
        values = dict(
            flow=flow,
            email="updated@example.invalid",
            version=booking.customer.revision,
            request_key=key,
        )
        result = correct_email(**values)
        self.assertEqual(correct_email(**values).pk, result.pk)
        booking.customer.refresh_from_db()
        self.assertEqual(booking.customer.email, "updated@example.invalid")
        self.assertEqual(booking.customer.previous_email, "test@example.invalid")
        original = MessageDelivery.objects.exclude(pk=result.pk).get()
        self.assertIsNone(claim(original.pk))
        self.assertEqual(MessageDelivery.objects.filter(state="queued").count(), 1)
        self.assertEqual(result.booking_id, booking.pk)

    def test_other_creation_key_or_duplicate_current_email_cannot_retarget_customer(self):
        flow, booking = self.completed()
        Customer.objects.create(
            last_name="Another", phone="2025550166", email="occupied@example.invalid"
        )
        with self.assertRaises(ValidationError):
            correct_email(
                flow=flow,
                email="occupied@example.invalid",
                version=booking.customer.revision,
                request_key=uuid.uuid4(),
            )
        with self.assertRaises((ValidationError, Booking.DoesNotExist)):
            correct_email(
                flow=dict(flow, booking_id=999999),
                email="updated@example.invalid",
                version=booking.customer.revision,
                request_key=uuid.uuid4(),
            )
        booking.customer.refresh_from_db()
        self.assertEqual(booking.customer.email, "test@example.invalid")
