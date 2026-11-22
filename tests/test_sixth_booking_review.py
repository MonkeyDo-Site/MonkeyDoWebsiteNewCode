"""Acceptance of the sixth review: consent, coverage, navigation and balance-only retry."""

import hashlib
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.communications.content import booking_confirmation
from core.communications.presentation import confirmation_html
from core.models import Booking, FinancialPosting, PaymentOperation
from core.payments import remainders
from core.payments.checkout import summary
from core.payments.policy import VERSION as PAYMENT_VERSION
from core.payments.setup import flow_identity, selected_consent
from core.public_booking import review_quote, submit_booking
from core.public_booking_views import SESSION_KEY, save
from core.waivers.coverage_forms import CoverageForm
from core.waivers.models import WaiverSignature, WaiverVersion
from core.waivers.services import approved_version
from tests import test_completed_public_booking as fixtures
from tests import test_remaining_payments as remaining
from tests import test_waivers as waiver_fixtures
from tests.helpers import verified_owner_login
from tests.test_owner_accounts import STORAGES

MemoryEvidence = waiver_fixtures.MemoryEvidence

SETTINGS = dict(
    STORAGES=STORAGES,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
    BANQUEST_TOKENIZATION_PUBLIC_KEY="pk_synthetic",
)


@override_settings(**SETTINGS)
class SixthBookingTests(TestCase):
    setUp = fixtures.CompletedPublicBookingTests.setUp
    create = fixtures.CompletedPublicBookingTests.create
    flow = fixtures.CompletedPublicBookingTests.flow
    ready = fixtures.CompletedPublicBookingTests.ready
    card = fixtures.CompletedPublicBookingTests.card
    save_card = fixtures.CompletedPublicBookingTests.save_card
    gateway = fixtures.CompletedPublicBookingTests.gateway
    signing_data = waiver_fixtures.WaiverTests.signing_data

    def store(self, flow):
        session = self.client.session
        session[SESSION_KEY] = flow
        session.save()

    def bare_flow(self):
        flow = self.flow()
        flow.update(
            session_id=self.create().pk,
            stage="waiver",
            details=dict(
                children=1, adults=1, babies=0, socks=0, supervised=False, expected_method="card"
            ),
        )
        flow["quote"] = review_quote(flow, flow["details"])
        return flow

    def legacy(self, flow, *, expired=False):
        version = approved_version()
        old, _ = WaiverVersion.objects.get_or_create(
            code="MD-WAIVER-2026-01",
            defaults=dict(
                legal_html=version.legal_html,
                acknowledgments={"adult": "Earlier acknowledgment"},
                text_hash="1" * 64,
                source_hash=version.source_hash,
            ),
        )
        return WaiverSignature.objects.create(
            version=old,
            request_key=uuid.uuid4(),
            fingerprint=uuid.uuid4().hex * 2,
            flow_hash=flow_identity(flow)[0],
            signer_name="Prior Guardian",
            signer_email="prior@example.invalid",
            signer_phone="2025550101",
            relationship="Parent",
            minors=["Test Child"],
            adult_accepted=True,
            waiver_accepted=True,
            electronic_accepted=True,
            signed_at=timezone.now() - timedelta(days=366 if expired else 10),
            valid_until=timezone.now() + timedelta(days=-1 if expired else 350),
            delete_after=timezone.now() + timedelta(days=360),
            object_key="staging/" + uuid.uuid4().hex,
            evidence_hash=hashlib.sha256(b"historical evidence").hexdigest(),
            state="signed",
        )

    def test_new_and_expired_customers_must_sign_even_when_requesting_shared_link(self):
        flow = self.bare_flow()
        for expired in (False, True):
            if expired:
                self.legacy(flow, expired=True)
            form = CoverageForm({"share_requested": "on"}, flow=flow)
            self.assertFalse(form.is_valid())
            self.assertIn("sign_now", form.errors)
            form = CoverageForm({"sign_now": "on", "share_requested": "on"}, flow=flow)
            self.assertTrue(form.is_valid(), form.errors)
            self.store(flow)
            page = self.client.get(reverse("customer_booking"))
            self.assertContains(page, "Please select option 1 or both options:")
            self.assertNotContains(page, "Continue to payment")

    def test_legacy_and_mixed_coverage_survive_new_acknowledgment_without_rewriting_evidence(self):
        flow = self.bare_flow()
        current = self.legacy(flow)
        self.legacy(flow, expired=True)
        form = CoverageForm({"use_existing": "on"}, flow=flow)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.has_expired)
        self.assertEqual([x.pk for x in form.signatures], [current.pk])
        self.store(flow)
        page = self.client.get(reverse("customer_booking"))
        self.assertContains(page, "Some waivers you signed in the past have expired")
        self.assertContains(page, "Prior Guardian")
        current.refresh_from_db()
        self.assertEqual(current.signer_email, "prior@example.invalid")
        self.assertEqual(current.version_id, "MD-WAIVER-2026-01")

    def test_signing_redirects_to_coverage_confirmation_and_never_repeats_the_legal_form(self):
        flow = self.bare_flow()
        self.store(flow)
        data = self.signing_data() | {"wizard_key": flow["key"], "wizard_stage": "waiver"}
        with patch("core.waivers.services.EvidenceStore", return_value=MemoryEvidence()):
            response = self.client.post(reverse("customer_waiver"), data, follow=True)
        self.assertContains(response, "Thank you! Your electronic waiver has been signed")
        self.assertNotContains(response, "Please read the complete waiver")
        signature = WaiverSignature.objects.get()
        self.assertEqual(signature.signer_email, "")
        self.assertEqual(signature.signer_phone, "")
        self.assertNotContains(response, 'name="signer_email"')
        self.assertFalse(Booking.objects.exists())
        response = self.client.post(
            reverse("customer_waiver_complete"),
            {"wizard_key": flow["key"], "wizard_stage": "waiver", "coverage": "yes"},
            follow=True,
        )
        self.assertContains(response, "Payment Details")
        self.assertFalse(FinancialPosting.objects.exists())

    def test_adult_only_signs_the_same_form_without_self_choice_or_contact_fields(self):
        flow = self.bare_flow()
        flow["details"].update(children=0, adults=1)
        flow["quote"] = review_quote(flow, flow["details"])
        self.store(flow)
        page = self.client.get(reverse("customer_waiver"))
        self.assertContains(page, 'name="minors"')
        self.assertContains(page, 'name="relationship"')
        self.assertNotContains(page, ">Self<")
        self.assertNotContains(page, 'name="signer_email"')
        self.assertNotContains(page, 'name="signer_phone"')
        data = self.signing_data(minors="", relationship="") | {
            "wizard_key": flow["key"],
            "wizard_stage": "waiver",
        }
        with patch("core.waivers.services.EvidenceStore", return_value=MemoryEvidence()):
            self.assertEqual(self.client.post(reverse("customer_waiver"), data).status_code, 302)
        self.assertEqual(WaiverSignature.objects.get().relationship, "Attending adult")

    def test_payment_method_switch_preserves_signatures_but_requires_fresh_policy_acceptance(self):
        flow = self.ready()
        flow["stage"] = "review"
        self.store(flow)
        response = self.client.post(
            reverse("customer_payment_method"),
            {"wizard_key": flow["key"], "wizard_stage": "review", "expected_method": "cash"},
            follow=True,
        )
        self.assertContains(response, "backup credit card")
        self.assertEqual(WaiverSignature.objects.count(), 1)
        changed = self.client.session[SESSION_KEY]
        self.assertEqual(changed["waiver_signatures"], flow["waiver_signatures"])
        self.assertEqual(changed["quote"]["processing_fee"], "0.00")
        self.assertTrue(changed["payment_method_changed"])
        self.assertContains(response, "data-confirm-booking disabled")
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            page = self.client.post(
                reverse("customer_card_setup"),
                data={
                    "wizard_key": flow["key"],
                    "wizard_stage": "review",
                    "policy_version": PAYMENT_VERSION,
                    "method": str(selected_consent(flow).method_id),
                    "agree_payment": True,
                    "agree_cancellation": True,
                },
                content_type="application/json",
            )
        self.assertEqual(page.status_code, 200, page.content)
        self.assertNotIn("payment_method_changed", self.client.session[SESSION_KEY])
        self.assertFalse(FinancialPosting.objects.exists())

    def test_primary_card_has_no_alternate_payment_checkbox_and_confirm_is_initially_disabled(self):
        flow = self.bare_flow()
        flow["stage"] = "review"
        self.store(flow)
        page = self.client.get(reverse("customer_booking"))
        self.assertContains(page, 'type="hidden" name="agree_payment"')
        self.assertNotContains(page, "I agree to this payment policy")
        self.assertNotContains(page, "backup credit card for each booking")
        self.assertContains(page, "data-confirm-booking disabled")
        self.assertContains(page, "Total due at arrival")
        self.assertContains(
            page,
            "Card will be charged at arrival. Save your card first, then confirm your booking.",
        )
        self.assertContains(page, "Save card securely", count=1)
        self.assertNotContains(page, "Estimated total at arrival")
        self.assertIn("no-store", page.headers["Cache-Control"])

    def test_backup_card_uses_save_action_without_disclaimer_or_payment_checkbox(self):
        flow = self.bare_flow()
        flow["stage"] = "review"
        flow["details"]["expected_method"] = "cash"
        flow["quote"] = review_quote(flow, flow["details"])
        self.store(flow)
        page = self.client.get(reverse("customer_booking"))
        self.assertNotContains(page, "A card saved only for this booking")
        self.assertNotContains(page, "I agree to this payment policy")
        self.assertNotContains(page, "create a verification hold")
        self.assertContains(page, "Saving a backup card does not charge it.")
        self.assertContains(page, "I understand the Monkey Do cancellation policy")
        self.assertContains(page, "Save card securely", count=1)
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            payload = {
                "wizard_key": flow["key"],
                "wizard_stage": "review",
                "policy_version": PAYMENT_VERSION,
                "request_key": str(uuid.uuid4()),
                "nonce": "nonce-Synthetic",
                "expiry_month": 12,
                "expiry_year": 2035,
                "agree_cancellation": True,
                "retain": False,
            }
            response = self.client.post(
                reverse("customer_card_setup"), payload, content_type="application/json"
            )
            self.assertEqual(response.status_code, 200, response.content)
            gateway.return_value.charge.assert_not_called()
        from core.payments.models import PaymentConsent

        accepted = PaymentConsent.objects.get()
        self.assertTrue(accepted.payment_accepted)
        self.assertTrue(accepted.cancellation_accepted)
        self.assertIn(
            "explicitly selecting Save card securely",
            accepted.policy.text["public_payment_acceptance"],
        )
        self.assertFalse(FinancialPosting.objects.exists())

    def test_sandbox_acknowledgment_is_absent_from_production_form(self):
        from core.public_booking_views import CompletedConfirmForm

        self.assertIn("acknowledge_test", CompletedConfirmForm().fields)
        with override_settings(APP_ENV="production"):
            self.assertNotIn("acknowledge_test", CompletedConfirmForm().fields)

    def test_confirmation_emails_have_one_total_conditional_socks_and_escaped_branded_html(self):
        flow = self.ready()
        booking = submit_booking(flow)
        for method in ("card", "cash", "zelle"):
            booking.expected_method = method
            text = booking_confirmation(booking)
            self.assertEqual(text.count("Your total is $"), 1)
            self.assertNotIn("Estimated total", text)
            self.assertNotIn("Staff will review", text)
            self.assertIn("Please remember to bring along your grip socks.", text)
            html = confirmation_html(text + "\n\n<script>alert(1)</script>")
            self.assertIn("#ad415d", html)
            self.assertIn("<strong>Your total is", html)
            self.assertNotIn("<script>", html)
            self.assertIn("&lt;script&gt;", html)
        booking.socks = 2
        text = booking_confirmation(booking)
        self.assertNotIn("Please remember to bring", text)
        self.assertNotIn("Grip socks: Pick up", text)

    def test_shared_parent_completion_uses_link_not_contact_and_hides_the_signing_form(self):
        from core.waivers.services import create_share

        flow = self.ready()
        booking = submit_booking(flow)
        _, token = create_share(actor=self.owner, booking_id=booking.pk)
        url = reverse("shared_waiver", args=[token])
        page = self.client.get(url)
        self.assertNotContains(page, 'name="signer_email"')
        self.assertNotContains(page, 'name="signer_phone"')
        data = self.signing_data(signer_name="Independent Parent")
        with patch("core.waivers.services.EvidenceStore", return_value=MemoryEvidence()):
            page = self.client.post(url, data, follow=True)
        self.assertContains(page, "Thank you. Your electronic waiver has been saved.")
        self.assertContains(page, "Appointment:")
        self.assertNotContains(page, "Please read the complete waiver")
        self.assertNotContains(page, "Sign the waiver")
        self.assertNotContains(page, booking.customer.email)
        signature = WaiverSignature.objects.get(signer_name="Independent Parent")
        self.assertEqual(signature.signer_email, "")
        notice = booking.messages.get(kind="waiver_completed")
        self.assertEqual(notice.recipient, booking.customer.email)
        self.assertIn("Independent Parent", notice.text_body)

    def test_browser_checkpoints_restore_inputs_and_reject_other_flow_or_forward_after_edits(self):
        from django.test import RequestFactory

        from core.booking_navigation import restore

        flow = self.bare_flow()
        request = RequestFactory().get("/")
        request.session = self.client.session
        flow["stage"] = "details"
        save(request, flow)
        flow["stage"] = "waiver"
        save(request, flow)
        request.GET = {"step": "details", "flow": flow["key"]}
        restored, response = restore(request, flow)
        self.assertIsNone(response)
        self.assertEqual(restored["details"], flow["details"])
        restored["navigation_revision"] = 1
        request.GET = {"step": "waiver", "flow": flow["key"]}
        _, response = restore(request, restored)
        self.assertEqual(response.status_code, 302)
        request.GET = {"step": "details", "flow": str(uuid.uuid4())}
        _, response = restore(request, flow)
        self.assertEqual(response.status_code, 302)


@override_settings(**SETTINGS)
class OwnerRetryTests(TestCase):
    setUp = remaining.RemainingPaymentTests.setUp
    create = remaining.RemainingPaymentTests.create
    flow = remaining.RemainingPaymentTests.flow
    card = remaining.RemainingPaymentTests.card
    save_card = remaining.RemainingPaymentTests.save_card
    gateway = remaining.RemainingPaymentTests.gateway
    ready = remaining.RemainingPaymentTests.ready
    booking = remaining.RemainingPaymentTests.booking
    arrival_inputs = remaining.RemainingPaymentTests.arrival_inputs
    act = remaining.RemainingPaymentTests.act
    decline = remaining.RemainingPaymentTests.decline

    def test_owner_retry_reviews_unpaid_amount_and_is_idempotent_without_inline_charge(self):
        booking = self.booking()
        checkout = self.act(booking, self.arrival_inputs(booking))
        original = checkout.sale.operations.get()
        self.decline(original)
        self.assertTrue(summary(booking)["can_retry"])
        verified_owner_login(self.client, self.owner)
        with patch("core.payments.operations.Gateway") as gateway:
            page = self.client.get(reverse("booking_retry_card", args=[booking.pk]))
            self.assertContains(page, "Retry card")
            self.assertEqual(PaymentOperation.objects.count(), 1)
            values = {"request_key": str(uuid.uuid4()), "method": "card", "context": "follow_up"}
            page = self.client.post(reverse("booking_retry_card", args=[booking.pk]), values)
            self.assertEqual(page.context["reviewed"]["amount"], str(original.amount))
            values |= {
                "reviewed_hash": page.context["form"]["reviewed_hash"].value(),
                "confirm_review": "1",
            }
            result = self.client.post(reverse("booking_retry_card", args=[booking.pk]), values)
            self.assertEqual(result.status_code, 302)
            self.client.post(reverse("booking_retry_card", args=[booking.pk]), values)
            gateway.assert_not_called()
        self.assertEqual(PaymentOperation.objects.count(), 2)
        original.refresh_from_db()
        self.assertEqual(original.state, "declined")
        self.assertFalse(summary(booking)["can_retry"])
        self.assertEqual(FinancialPosting.objects.count(), 0)

    def test_retry_is_owner_only_and_pending_or_unknown_balance_is_not_retryable(self):
        booking = self.booking()
        checkout = self.act(booking, self.arrival_inputs(booking))
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.get(reverse("booking_retry_card", args=[booking.pk])).status_code, 403
        )
        with self.assertRaises(PermissionDenied):
            remainders.preview(
                actor=self.staff, booking_id=booking.pk, method="card", retry_declined=True
            )
        self.assertFalse(summary(booking)["can_retry"])
        with self.assertRaises(ValidationError):
            remainders.preview(
                actor=self.owner, booking_id=booking.pk, method="card", retry_declined=True
            )
        self.assertEqual(checkout.sale.operations.get().amount, Decimal("16.47"))
        from core.payments.ledger import record_result

        record_result(
            operation_id=checkout.sale.operations.get().pk, state="unknown", source="provider"
        )
        self.assertFalse(summary(booking)["can_retry"])
        with self.assertRaises(ValidationError):
            remainders.preview(
                actor=self.owner, booking_id=booking.pk, method="card", retry_declined=True
            )
