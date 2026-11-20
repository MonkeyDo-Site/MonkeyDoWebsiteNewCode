"""Staff secure entry is separate from public tabs and records staff-reviewed consent."""

import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from core.booking_management import create_test_booking
from core.models import FinancialPosting, MessageDelivery, PaymentConsent
from core.payments.policy import VERSION
from core.payments.staff_setup import session_key
from tests import test_payment_setup as fixtures
from tests.test_owner_accounts import STORAGES


@override_settings(
    STORAGES=STORAGES,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
    BANQUEST_TOKENIZATION_PUBLIC_KEY="pk_fake_sandbox",
)
class StaffSetupTests(TestCase):
    setUp = fixtures.CardSetupTests.setUp
    create = fixtures.CardSetupTests.create
    card = fixtures.CardSetupTests.card
    gateway = fixtures.CardSetupTests.gateway

    def booking(self):
        return create_test_booking(
            actor=self.staff,
            customer=self.customer,
            session_id=self.create().pk,
            children=1,
            adults=1,
            creation_key=uuid.uuid4(),
            workflow="integrated_v1",
        )

    def enter_card(self, booking):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("staff_booking_setup", args=[booking.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "policies have been reviewed with the customer")
        flow = self.client.session[session_key(booking.pk)]
        values = {
            "wizard_key": flow["key"],
            "wizard_stage": "review",
            "policy_version": VERSION,
            "request_key": str(uuid.uuid4()),
            "nonce": "nonce-Synthetic",
            "expiry_month": 12,
            "expiry_year": 2035,
            "agree_payment": True,
            "agree_cancellation": True,
        }
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            response = self.client.post(
                reverse("staff_card_setup", args=[booking.pk]),
                values,
                content_type="application/json",
            )
            gateway.return_value.charge.assert_not_called()
        self.assertEqual(response.status_code, 200)
        return self.client.session[session_key(booking.pk)]

    def test_staff_confirm_can_leave_waiver_pending_and_queue_multiple_parent_instructions(self):
        booking = self.booking()
        flow = self.enter_card(booking)
        accepted = PaymentConsent.objects.get(pk=flow["payment_consent"])
        self.assertEqual(accepted.source, "staff")
        self.assertEqual(accepted.actor_id, self.staff.pk)
        values = {
            "wizard_key": flow["key"],
            "payment_consent": flow["payment_consent"],
            "waiver_type": "multiple",
            "confirm": "on",
        }
        url = reverse("staff_booking_setup", args=[booking.pk])
        self.assertEqual(self.client.post(url, values).status_code, 302)
        self.assertEqual(self.client.post(url, values).status_code, 302)
        booking.refresh_from_db()
        self.assertFalse(booking.setup_pending)
        self.assertFalse(booking.waiver_review.coverage_confirmed)
        self.assertEqual(booking.card_agreement.method.customer_id, self.customer.pk)
        message = MessageDelivery.objects.get()
        self.assertEqual(message.kind, "booking_waiver")
        self.assertTrue(message.unsigned_waiver)
        self.assertIn("https://staging.monkeydoplay.com/waiver/shared/", message.text_body)
        self.assertEqual(booking.waiver_share_links.count(), 1)
        self.assertFalse(FinancialPosting.objects.exists())

    def test_public_endpoint_cannot_use_a_staff_booking_flow(self):
        booking = self.booking()
        self.enter_card(booking)
        with patch("core.payments.setup.Gateway") as gateway:
            response = self.client.post("/book/card/setup/", {}, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        gateway.assert_not_called()

    def test_changed_booking_rejects_staff_card_exchange_before_provider_io(self):
        booking = self.booking()
        flow = self.enter_card(booking)
        booking.edit_version += 1
        booking.save(update_fields=["edit_version"])
        with patch("core.payments.setup.Gateway") as gateway:
            response = self.client.post(
                reverse("staff_card_setup", args=[booking.pk]),
                {
                    "wizard_key": flow["key"],
                    "wizard_stage": "review",
                    "policy_version": VERSION,
                    "request_key": str(uuid.uuid4()),
                    "nonce": "nonce-Different",
                    "expiry_month": 12,
                    "expiry_year": 2035,
                    "agree_payment": True,
                    "agree_cancellation": True,
                },
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 400)
        gateway.assert_not_called()

    def test_staff_without_customer_email_is_not_given_a_fabricated_message_destination(self):
        self.customer.email = ""
        self.customer.save(update_fields=["email"])
        booking = self.booking()
        flow = self.enter_card(booking)
        response = self.client.post(
            reverse("staff_booking_setup", args=[booking.pk]),
            {
                "wizard_key": flow["key"],
                "payment_consent": flow["payment_consent"],
                "waiver_type": "single",
                "confirm": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertFalse(booking.setup_pending)
        self.assertFalse(MessageDelivery.objects.exists())
