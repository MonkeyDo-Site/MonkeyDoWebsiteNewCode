"""Online group booking holds capacity before all parents sign, with no online charge."""

import re
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.availability import occupancy
from core.booking_email import correct_email
from core.models import FinancialPosting, MessageDelivery
from core.public_booking import submit_booking
from core.waivers.coverage_forms import CoverageForm
from core.waivers.services import share_for_token, sign
from tests import test_completed_public_booking as fixtures
from tests.test_owner_accounts import STORAGES
from tests.test_waivers import MemoryEvidence, WaiverTests


@override_settings(
    STORAGES=STORAGES,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)
class PublicGroupWaiverTests(TestCase):
    setUp = fixtures.CompletedPublicBookingTests.setUp
    create = fixtures.CompletedPublicBookingTests.create
    flow = fixtures.CompletedPublicBookingTests.flow
    card = fixtures.CompletedPublicBookingTests.card
    save_card = fixtures.CompletedPublicBookingTests.save_card
    gateway = fixtures.CompletedPublicBookingTests.gateway
    ready = fixtures.CompletedPublicBookingTests.ready
    signing_data = WaiverTests.signing_data

    def pending(self):
        flow = self.ready()
        flow.update(
            stage="review", waiver_signatures=[], waiver_coverage=False, waiver_share_requested=True
        )
        return flow, submit_booking(flow)

    def test_shared_option_holds_places_and_queues_one_link_and_unsigned_pdf(self):
        flow, booking = self.pending()
        self.assertFalse(booking.setup_pending)
        self.assertFalse(booking.waiver_review.coverage_confirmed)
        self.assertTrue(booking.waiver_review.share_requested)
        self.assertIn("Waiver pending", booking.status_label)
        self.assertEqual(occupancy(booking.session)[:2], (booking.children, booking.adults))
        message = MessageDelivery.objects.get()
        self.assertEqual(message.kind, "booking_waiver")
        self.assertTrue(message.unsigned_waiver)
        self.assertIn("waiver link that you requested", message.text_body)
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertEqual(submit_booking(flow).pk, booking.pk)
        self.assertEqual(booking.waiver_share_links.count(), 1)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("bookings"), {"status": "waiver_pending"})
        self.assertEqual(response.context["bookings"].paginator.count, 1)

    def test_parent_signing_is_independent_and_does_not_release_or_rebook_places(self):
        _, booking = self.pending()
        body = MessageDelivery.objects.get().text_body
        token = re.search(r"/waiver/shared/([^/]+)/", body).group(1)
        self.assertEqual(share_for_token(token).booking_id, booking.pk)
        before = occupancy(booking.session)
        with patch("core.waivers.services.EvidenceStore", return_value=MemoryEvidence()):
            signature = sign(data=self.signing_data(signer_name="Other Parent"), share_token=token)
        self.assertTrue(booking.waiver_links.filter(signature=signature).exists())
        self.assertEqual(occupancy(booking.session), before)
        self.assertEqual(MessageDelivery.objects.filter(kind="waiver_completed").count(), 1)
        self.assertFalse(FinancialPosting.objects.exists())

    def test_share_choice_can_continue_without_signature_but_ordinary_choice_cannot(self):
        flow = self.ready()
        flow["waiver_signatures"] = []
        group = CoverageForm({"share_requested": "on"}, flow=flow)
        self.assertTrue(group.is_valid(), group.errors)
        ordinary = CoverageForm({"additional_minors": "no", "coverage_confirmed": "on"}, flow=flow)
        self.assertFalse(ordinary.is_valid())
        flow.update(waiver_share_requested=False, waiver_coverage=False)
        with self.assertRaises(ValidationError):
            submit_booking(flow)

    def test_public_share_creation_is_scoped_and_email_correction_keeps_group_instructions(self):
        import uuid

        from core.waivers.services import create_share

        flow, booking = self.pending()
        with self.assertRaises(ValidationError):
            create_share(actor=None, booking_id=booking.pk, flow=dict(flow, key=str(uuid.uuid4())))
        flow.update(stage="done", booking_id=booking.pk)
        result = correct_email(
            flow=flow,
            email="group-corrected@example.invalid",
            version=booking.customer.revision,
            request_key=uuid.uuid4(),
        )
        self.assertEqual(result.kind, "booking_waiver")
        self.assertTrue(result.unsigned_waiver)
        self.assertIn("/waiver/shared/", result.text_body)
