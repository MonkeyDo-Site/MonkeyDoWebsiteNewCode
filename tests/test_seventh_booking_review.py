"""Seventh review: cash identity, explicit manual refunds and coverage reuse."""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import FinancialPosting, PaymentOperation, ZelleReceipt
from core.payments import zelle
from core.payments.checkout import confirm, preview
from core.waivers.coverage_forms import CoverageForm
from core.waivers.paper import active_customer_waivers, record
from tests import test_booking_checkout as fixtures
from tests.helpers import verified_owner_login
from tests.test_owner_accounts import STORAGES


@override_settings(
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
    STORAGES=STORAGES,
)
class SeventhReviewTests(TestCase):
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

    def receipt(self, b, value="20.00", key=None):
        return zelle.record_receipt(
            actor=self.staff,
            booking_id=b.pk,
            request_key=key or uuid.uuid4(),
            value=value,
            sender_name="Test Sender",
            verified=True,
        )

    def test_receipt_holds_money_without_arrival_and_replay_cannot_duplicate_it(self):
        b = self.booking()
        key = uuid.uuid4()
        r = self.receipt(b, key=key)
        self.receipt(b, key=key)
        b.refresh_from_db()
        self.assertEqual(b.attendance, "")
        self.assertEqual(ZelleReceipt.objects.count(), 1)
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertEqual(zelle.facts(b)["refund_due"], 0)
        with self.assertRaises(ValidationError):
            self.receipt(b, value="21.00", key=key)
        self.assertEqual(r.received_on, timezone.localdate())

    def test_overpayment_is_applied_once_and_refund_notice_resolves_only_on_completion(self):
        b = self.booking()
        self.receipt(b)
        data = self.arrival_inputs(b, method="zelle")
        result = self.act(b, data)
        b.refresh_from_db()
        self.assertEqual(zelle.facts(b)["refund_due"], Decimal("4.01"))
        self.assertEqual(result.sale.operations.count(), 1)
        self.assertEqual(result.sale.operations.get().amount, Decimal("15.99"))
        self.assertEqual(len(zelle.refund_notices()), 1)
        with self.assertRaises(PermissionDenied):
            zelle.complete_refund(
                actor=self.staff,
                booking_id=b.pk,
                request_key=uuid.uuid4(),
                reviewed_amount="4.01",
                confirmed=True,
            )
        key = uuid.uuid4()
        zelle.complete_refund(
            actor=self.owner,
            booking_id=b.pk,
            request_key=key,
            reviewed_amount="4.01",
            confirmed=True,
        )
        zelle.complete_refund(
            actor=self.owner,
            booking_id=b.pk,
            request_key=key,
            reviewed_amount="4.01",
            confirmed=True,
        )
        self.assertEqual(zelle.facts(b)["refund_due"], 0)
        self.assertFalse(zelle.refund_notices())
        self.assertEqual(result.sale.operations.count(), 1)

    def test_partial_prepayment_charges_only_card_balance_and_keeps_tax_fee_allocation(self):
        b = self.booking()
        self.receipt(b, value="10")
        result = self.act(b, self.arrival_inputs(b))
        ops = list(result.sale.operations.all())
        self.assertEqual(len(ops), 2)
        self.assertEqual(result.sale.operations.get(tender="zelle").amount, Decimal("10"))
        card = result.sale.operations.get(tender="card")
        self.assertLess(card.amount, Decimal("6.47"))
        self.assertGreater(card.amount, Decimal("5.99"))
        self.assertEqual(sum(o.amount for o in ops), result.sale.total)

    def test_changed_prepayment_invalidates_reviewed_hash_before_any_arrival_charge(self):
        b = self.booking()
        data = self.arrival_inputs(b)
        digest = preview(actor=self.staff, booking_id=b.pk, kind="arrival", data=data)[-1]
        self.receipt(b, value="10")
        with self.assertRaises(ValidationError):
            confirm(
                actor=self.staff,
                booking_id=b.pk,
                kind="arrival",
                data=data,
                request_key=uuid.uuid4(),
                reviewed_hash=digest,
                confirmed=True,
            )
        self.assertFalse(PaymentOperation.objects.exists())
        b.refresh_from_db()
        self.assertFalse(b.attendance)

    def test_cancellation_applies_prepaid_fee_then_refunds_excess_and_email_is_optional(self):
        b = self.booking()
        self.receipt(b)
        self.act(
            b, {"charge_fee": True, "method": "card", "send_email": False}, kind="cancellation"
        )
        b.refresh_from_db()
        self.assertEqual(zelle.facts(b)["refund_due"], Decimal("17"))
        self.assertFalse(b.messages.filter(kind="booking_cancelled").exists())
        self.assertEqual(PaymentOperation.objects.get().tender, "zelle")

    def test_no_fee_cancellation_returns_entire_prepayment_and_selected_email_is_truthful(self):
        b = self.booking()
        self.receipt(b)
        self.act(
            b, {"charge_fee": False, "method": "card", "send_email": True}, kind="cancellation"
        )
        b.refresh_from_db()
        self.assertEqual(zelle.facts(b)["refund_due"], Decimal("20"))
        mail = b.messages.get(kind="booking_cancelled")
        self.assertIn("has not yet been refunded", mail.text_body)
        self.assertIn("No cancellation/no-show fee", mail.text_body)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_named_paper_waiver_reuses_customer_coverage_and_never_creates_electronic_evidence(
        self,
    ):
        b = self.booking()
        item = record(
            actor=self.staff,
            booking_id=b.pk,
            request_key=uuid.uuid4(),
            signer_name="Test Parent",
            relationship="Parent",
            minors="Mindy\nGoldy",
            signed_on=timezone.localdate(),
            paper_signed=True,
        )
        self.assertEqual(item.signature_method, "paper")
        self.assertIn(item, active_customer_waivers(b))
        with self.assertRaises(ValidationError):
            record(
                actor=self.staff,
                booking_id=b.pk,
                request_key=uuid.uuid4(),
                signer_name="Test Guardian",
                relationship="Legal guardian",
                minors="Mindy",
                signed_on=timezone.localdate(),
                paper_signed=True,
            )

    def test_arrival_page_opens_without_financial_writes_and_shows_four_short_fields(self):
        b = self.booking()
        verified_owner_login(self.client, self.owner)
        response = self.client.get(reverse("booking_arrival", args=[b.pk]))
        self.assertEqual(response.status_code, 200)
        for label in (
            "Active customer waivers",
            "Who arrived?",
            "Visit payment details",
            "data-arrival-live",
        ):
            self.assertContains(response, label)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_partial_zelle_cannot_be_recorded_as_the_full_payment(self):
        b = self.booking()
        self.receipt(b, value="10")
        with self.assertRaisesMessage(ValidationError, "Only $10.00"):
            self.act(b, self.arrival_inputs(b, method="zelle"))
        b.refresh_from_db()
        self.assertFalse(b.attendance)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_owner_supervised_exception_is_booking_scoped_and_public_limits_remain(self):
        from core.booking_management import assert_capacity, edit_test_booking

        b = self.booking()
        slot = b.session
        slot.play_mode = "accompanied"
        slot.supervised_capacity = 0
        slot.starts_at = timezone.now() - timedelta(minutes=15)
        slot.save()
        values = dict(
            booking_id=b.pk,
            version=b.edit_version,
            children=1,
            adults=0,
            babies=0,
            socks=0,
            expected_method="card",
            supervised=True,
            supervised_exception=True,
        )
        with self.assertRaises(ValidationError):
            edit_test_booking(actor=self.staff, **values)
        edit_test_booking(actor=self.owner, **values)
        b.refresh_from_db()
        slot.refresh_from_db()
        self.assertTrue(b.supervised)
        self.assertEqual(slot.play_mode, "accompanied")
        self.assertEqual(slot.supervised_capacity, 0)
        with self.assertRaises(ValidationError):
            assert_capacity(slot, actor=None, children=1, adults=0, supervised=True)
        with self.assertRaises(ValidationError):
            assert_capacity(
                slot, actor=self.owner, booking_id=b.pk, children=36, adults=0, supervised=True
            )

    def test_inline_receipt_returns_json_and_preserves_unconfirmed_arrival(self):
        b = self.booking()
        verified_owner_login(self.client, self.owner)
        response = self.client.post(
            reverse("booking_zelle_receipt", args=[b.pk]),
            {
                "request_key": uuid.uuid4(),
                "value": "5.00",
                "sender_name": "Test Sender",
                "verified": "on",
            },
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["received"], "5.00")
        b.refresh_from_db()
        self.assertFalse(b.attendance)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_reviewed_advance_receipt_and_manual_refund_work_under_runtime_grants(self):
        from tests.test_payment_runtime_grants import RuntimeRoleMixin

        b = self.booking()
        with RuntimeRoleMixin.runtime_role(self):
            self.receipt(b, value="20")
            self.act(b, self.arrival_inputs(b, method="zelle"))
            zelle.complete_refund(
                actor=self.owner,
                booking_id=b.pk,
                request_key=uuid.uuid4(),
                reviewed_amount="4.01",
                confirmed=True,
            )
        self.assertEqual(zelle.facts(b)["refunded"], Decimal("4.01"))

    def test_paper_only_coverage_can_be_reused_by_the_same_public_customer(self):

        b = self.booking()
        # Isolate paper coverage from the original fictional electronic signature.
        record(
            actor=self.owner,
            booking_id=b.pk,
            request_key=uuid.uuid4(),
            signer_name="Test Parent",
            relationship="Parent",
            minors="Mindy",
            signed_on=timezone.localdate(),
            paper_signed=True,
        )
        flow = self.flow()
        flow.update(session_id=b.session_id, details={"children": 1, "babies": 0}, stage="waiver")
        form = CoverageForm({"use_existing": "on"}, flow=flow)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(any(s.signature_method == "paper" for s in form.signatures))
        other = self.flow(new=True)
        other.update(session_id=b.session_id, details={"children": 1, "babies": 0}, stage="waiver")
        other_form = CoverageForm({"use_existing": "on"}, flow=other)
        self.assertFalse(other_form.is_valid())
