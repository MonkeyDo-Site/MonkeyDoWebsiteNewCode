"""Completed public reservation binds setup/evidence atomically and never charges admission."""

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Booking, FinancialPosting, MessageDelivery
from core.public_booking import review_quote, submit_booking
from core.waivers.services import approved_version, sign
from tests import test_payment_setup as card_fixtures
from tests.test_waivers import MemoryEvidence


@override_settings(
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)
class CompletedPublicBookingTests(TestCase):
    setUp = card_fixtures.CardSetupTests.setUp
    create = card_fixtures.CardSetupTests.create
    flow = card_fixtures.CardSetupTests.flow
    card = card_fixtures.CardSetupTests.card
    save_card = card_fixtures.CardSetupTests.save_card
    gateway = card_fixtures.CardSetupTests.gateway

    def ready(self):
        flow = self.flow()
        flow["session_id"] = self.create().pk
        flow["details"] = dict(
            children=1, adults=1, babies=0, socks=0, supervised=False, expected_method="card"
        )
        flow["quote"] = review_quote(flow, flow["details"])
        version = approved_version()
        with patch("core.waivers.services.EvidenceStore", return_value=MemoryEvidence()):
            signature = sign(
                data=dict(
                    request_key="cbaed173-39ef-4442-a742-30ad88b95183",
                    version=version.pk,
                    text_hash=version.text_hash,
                    signer_name="Test Guardian",
                    signer_email="guardian@example.invalid",
                    relationship="Parent",
                    minors="Test Child",
                    adult_accepted=True,
                    waiver_accepted=True,
                    electronic_accepted=True,
                ),
                flow=flow,
            )
        flow["waiver_signatures"] = [str(signature.pk)]
        flow["waiver_coverage"] = True
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            saved = self.save_card(flow)
            flow["payment_consent"] = str(saved.consent_id)
        return flow

    def test_completed_booking_saves_one_bound_card_and_waiver_and_queues_confirmation_without_payment(
        self,
    ):
        flow = self.ready()
        booking = submit_booking(flow)
        self.assertEqual(booking.workflow, "integrated_v1")
        self.assertFalse(booking.setup_pending)
        self.assertEqual(booking.card_agreement.method.customer_id, self.customer.pk)
        self.assertEqual(booking.waiver_links.count(), 1)
        self.assertTrue(booking.waiver_review.coverage_confirmed)
        self.assertEqual(MessageDelivery.objects.get().state, "queued")
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertEqual(booking.attendance, "")
        self.assertEqual(submit_booking(flow).pk, booking.pk)
        self.assertEqual(MessageDelivery.objects.count(), 1)

    def test_existing_profile_email_is_added_after_proof_bound_card_and_waiver_validation(self):
        self.customer.email = ""
        self.customer.save(update_fields=["email"])
        flow = self.ready()
        flow["contact_email"] = "newcurrent@example.invalid"
        booking = submit_booking(flow)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.email, "newcurrent@example.invalid")
        self.assertEqual(booking.card_agreement.method.customer_id, self.customer.pk)
        self.assertEqual(MessageDelivery.objects.get().recipient, self.customer.email)

    def test_incomplete_waiver_or_card_does_not_leave_a_confirmed_booking(self):
        flow = self.ready()
        flow["waiver_coverage"] = False
        with self.assertRaises(ValidationError):
            submit_booking(flow)
        self.assertFalse(Booking.objects.exists())

        self.assertFalse(MessageDelivery.objects.exists())
        flow["waiver_coverage"] = True
        flow.pop("payment_consent")
        with self.assertRaises(ValidationError):
            submit_booking(flow)
        self.assertFalse(Booking.objects.exists())

    def test_customer_pages_use_waiver_step_and_truthful_queued_confirmation(self):
        from core.public_booking_views import SESSION_KEY

        flow = self.ready()
        session = self.client.session
        session[SESSION_KEY] = flow
        session.save()
        response = self.client.post(
            reverse("customer_booking"),
            {
                "wizard_key": flow["key"],
                "wizard_stage": "details",
                "play_type": "open",
                "children": 1,
                "adults": 1,
                "babies": 0,
                "socks": 0,
                "expected_method": "card",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session[SESSION_KEY]["stage"], "waiver")
        response = self.client.get(reverse("customer_booking"))
        self.assertContains(response, "Waiver coverage")
        self.assertNotContains(response, "No card is collected")
        response = self.client.post(
            reverse("customer_booking"),
            {
                "wizard_key": flow["key"],
                "wizard_stage": "waiver",
                "signatures": flow["waiver_signatures"],
                "additional_minors": "no",
                "coverage_confirmed": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session[SESSION_KEY]["stage"], "review")
        response = self.client.get(reverse("customer_booking"))
        self.assertContains(response, "Secure card setup")
        self.assertContains(response, "Confirm sandbox booking")
        response = self.client.post(
            reverse("customer_booking"),
            {
                "wizard_key": flow["key"],
                "wizard_stage": "review",
                "flow_key": flow["key"],
                "payment_consent": flow["payment_consent"],
                "acknowledge_test": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your sandbox booking is saved")
        self.assertContains(response, "Your confirmation email is being prepared")
        self.assertNotContains(
            response, "No card, payment, waiver or confirmation email has been recorded"
        )
