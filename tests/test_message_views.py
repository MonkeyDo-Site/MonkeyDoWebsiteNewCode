"""Scoped confirmation resend, history permissions and current-contact snapshots."""

import uuid

from django.test import TestCase, override_settings
from django.urls import reverse

from core.communications.services import enqueue
from core.models import Customer, MessageDelivery
from tests import test_payment_ledger as fixtures
from tests.helpers import verified_owner_login


@override_settings(BOOKING_EMAIL_ENABLED=True, PAYMENT_SANDBOX_ENABLED=True, WAIVER_ENABLED=True)
class MessageViewTests(TestCase):
    setUp = fixtures.PaymentLedgerTests.setUp
    create = fixtures.PaymentLedgerTests.create
    sale = fixtures.PaymentLedgerTests.sale

    def message(self, kind="booking_confirmation"):
        self.sale()
        return enqueue(
            key=str(uuid.uuid4()),
            kind=kind,
            recipient=self.customer.email,
            subject="Your Monkey Do adventure is booked!",
            text="Initial attempt content",
            customer=self.customer,
            booking=self.booking,
        )

    def test_resend_is_booking_only_current_contact_and_idempotent(self):
        message = self.message()
        Customer.objects.filter(pk=self.customer.pk).update(email="updated@example.invalid")
        verified_owner_login(self.client, self.owner)
        url = reverse("message_detail", args=[message.pk])
        key = str(uuid.uuid4())
        first = self.client.post(url, {"request_key": key, "confirm": "on"})
        second = self.client.post(url, {"request_key": key, "confirm": "on"})
        self.assertEqual(first.status_code, 302)
        self.assertEqual(first.url, second.url)
        self.assertEqual(MessageDelivery.objects.count(), 2)
        queued = MessageDelivery.objects.exclude(pk=message.pk).get()
        self.assertEqual(queued.booking_id, self.booking.pk)
        self.assertEqual(queued.recipient, "updated@example.invalid")
        self.assertEqual(queued.state, "queued")
        self.assertIn("Your card will be charged upon arrival.", queued.text_body)
        self.assertNotIn("Actual payment received", queued.text_body)
        self.assertEqual(message.recipient, "test@example.invalid")

    def test_repeated_waiver_resend_does_not_create_more_links(self):
        message = self.message(kind="booking_waiver")
        verified_owner_login(self.client, self.owner)
        url = reverse("message_detail", args=[message.pk])
        values = {"request_key": str(uuid.uuid4()), "confirm": "on"}
        self.assertEqual(self.client.post(url, values).status_code, 302)
        self.assertEqual(self.client.post(url, values).status_code, 302)
        self.assertEqual(self.booking.waiver_share_links.count(), 1)
        queued = MessageDelivery.objects.exclude(pk=message.pk).get()
        self.assertIn("https://staging.monkeydoplay.com/waiver/shared/", queued.text_body)

    def test_staff_history_is_paged_and_owner_alert_is_private(self):
        message = self.message()
        alert = enqueue(
            key=str(uuid.uuid4()),
            kind="payment_issue",
            recipient="monkeydoplay@gmail.com",
            subject="Payment review",
            text="Safe owner notice",
            customer=self.customer,
        )
        self.client.force_login(self.staff)
        response = self.client.get(reverse("messages"), {"q": "202-555-0122", "per_page": 10})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["deliveries"].paginator.count, 1)
        self.assertContains(response, reverse("message_detail", args=[message.pk]))
        self.assertNotContains(response, reverse("message_detail", args=[alert.pk]))
        self.assertEqual(
            self.client.get(reverse("message_detail", args=[alert.pk])).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                reverse("message_detail", args=[alert.pk]),
                {"request_key": str(uuid.uuid4()), "confirm": "on"},
            ).status_code,
            403,
        )

    def test_missing_current_email_does_not_create_another_send_attempt(self):
        message = self.message()
        Customer.objects.filter(pk=self.customer.pk).update(email="")
        verified_owner_login(self.client, self.owner)
        response = self.client.post(
            reverse("message_detail", args=[message.pk]),
            {"request_key": str(uuid.uuid4()), "confirm": "on"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add a current customer email address")
        self.assertEqual(MessageDelivery.objects.count(), 1)
