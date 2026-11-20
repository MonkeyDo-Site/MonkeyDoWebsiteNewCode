"""Arrival/closure requires explicit reviewed action and preserves split funds on failure."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import BookingCheckout, FinancialPosting, PaymentOperation, PricingPolicy
from core.payments.checkout import confirm, preview
from core.payments.invoices import received, total
from core.payments.operations import execute
from core.public_booking import review_quote, submit_booking
from core.waivers.services import approved_version, set_paper, sign
from tests import test_completed_public_booking as fixtures
from tests.test_waivers import MemoryEvidence


@override_settings(
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)
class CheckoutTests(TestCase):
    setUp = fixtures.CompletedPublicBookingTests.setUp
    create = fixtures.CompletedPublicBookingTests.create
    flow = fixtures.CompletedPublicBookingTests.flow
    card = fixtures.CompletedPublicBookingTests.card
    save_card = fixtures.CompletedPublicBookingTests.save_card
    gateway = fixtures.CompletedPublicBookingTests.gateway
    ready = fixtures.CompletedPublicBookingTests.ready

    def booking(self, children=1):
        flow = self.ready()
        if children > 1:
            version = approved_version()
            with patch("core.waivers.services.EvidenceStore", return_value=MemoryEvidence()):
                signature = sign(
                    data=dict(
                        request_key=uuid.uuid4(),
                        version=version.pk,
                        text_hash=version.text_hash,
                        signer_name="Test Guardian",
                        signer_email="guardian@example.invalid",
                        relationship="Parent",
                        minors="\n".join("Test Child " + str(i) for i in range(children)),
                        adult_accepted=True,
                        waiver_accepted=True,
                        electronic_accepted=True,
                    ),
                    flow=flow,
                )
            flow["waiver_signatures"] = [str(signature.pk)]
            flow["details"]["children"] = children
            flow["quote"] = review_quote(flow, flow["details"])
        return submit_booking(flow)

    def arrival_inputs(self, booking, **changes):
        return {
            "children": booking.children,
            "adults": booking.adults,
            "babies": booking.babies,
            "socks": booking.socks,
            "method": "card",
            "waiver_confirmed": True,
            "override_capacity": False,
        } | changes

    def act(self, booking, data, kind="arrival", key=None):
        reviewed = preview(actor=self.staff, booking_id=booking.pk, kind=kind, data=data)
        return confirm(
            actor=self.staff,
            booking_id=booking.pk,
            kind=kind,
            data=data,
            request_key=key or uuid.uuid4(),
            reviewed_hash=reviewed[-1],
            confirmed=True,
        )

    def test_preview_and_waiver_no_do_not_mark_arrival_or_create_money(self):
        booking = self.booking()
        preview(
            actor=self.staff,
            booking_id=booking.pk,
            kind="arrival",
            data=self.arrival_inputs(booking),
        )
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "")
        self.assertFalse(BookingCheckout.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        with self.assertRaises(ValidationError):
            preview(
                actor=self.staff,
                booking_id=booking.pk,
                kind="arrival",
                data=self.arrival_inputs(booking, waiver_confirmed=False),
            )
        self.assertFalse(FinancialPosting.objects.exists())

    def test_cash_arrival_is_explicit_idempotent_and_resolves_booking_only_card_responsibility(
        self,
    ):
        booking = self.booking()
        data = self.arrival_inputs(booking, method="cash")
        key = uuid.uuid4()
        reviewed = preview(actor=self.staff, booking_id=booking.pk, kind="arrival", data=data)
        checkout = confirm(
            actor=self.staff,
            booking_id=booking.pk,
            kind="arrival",
            data=data,
            request_key=key,
            reviewed_hash=reviewed[-1],
            confirmed=True,
        )
        again = confirm(
            actor=self.staff,
            booking_id=booking.pk,
            kind="arrival",
            data=data,
            request_key=key,
            reviewed_hash=reviewed[-1],
            confirmed=True,
        )
        booking.refresh_from_db()
        self.assertEqual(checkout.pk, again.pk)
        self.assertEqual(booking.attendance, "arrived")
        self.assertEqual(received(checkout.sale), Decimal("15.99"))
        self.assertEqual(checkout.sale.processing_fee, Decimal("0"))
        self.assertIsNotNone(booking.card_agreement.resolved_at)
        self.assertEqual(FinancialPosting.objects.count(), 1)

    def test_failed_split_card_preserves_received_cash_and_remaining_balance(self):
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
            booking,
            self.arrival_inputs(booking, children=3, method="split", split={"cash": "40.00"}),
        )
        cash = checkout.sale.operations.get(tender="cash")
        card = checkout.sale.operations.get(tender="card")
        self.assertEqual(cash.state, "succeeded")
        self.assertEqual(cash.amount, Decimal("40"))
        self.assertEqual(card.amount, Decimal("35"))
        with patch("core.payments.operations.Gateway") as gateway:
            gateway.return_value.charge.return_value = {"status_code": "D"}
            execute(card.pk)
        self.assertEqual(received(checkout.sale), Decimal("40"))
        self.assertEqual(total(checkout.sale) - received(checkout.sale), Decimal("35"))
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "arrived")
        self.assertIsNone(booking.card_agreement.resolved_at)

    def test_fewer_children_adds_one_three_dollar_fee_without_taxing_it(self):
        booking = self.booking(children=3)
        checkout = self.act(booking, self.arrival_inputs(booking, children=2, method="cash"))
        self.assertEqual(checkout.sale.subtotal, Decimal("33"))
        self.assertEqual(checkout.sale.sales_tax, Decimal("1.98"))
        fee = checkout.sale.lines.get(category="partial_cancellation")
        self.assertFalse(fee.taxable)
        self.assertEqual(fee.net, Decimal("3"))
        self.assertEqual(fee.item_tax, Decimal("0"))

    def test_cancellation_choice_records_no_fee_or_queues_only_the_reviewed_fee(self):
        booking = self.booking(children=2)
        checkout = self.act(booking, {"charge_fee": True, "method": "card"}, kind="cancellation")
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "cancelled")
        self.assertEqual(checkout.sale.subtotal, Decimal("6"))
        self.assertEqual(checkout.sale.total, Decimal("6.18"))
        self.assertEqual(checkout.sale.sales_tax, Decimal("0"))
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertEqual(checkout.sale.operations.get().purpose, "cancellation")

    def test_no_show_without_fee_has_no_payment_and_can_only_follow_session_start(self):
        booking = self.booking()
        with self.assertRaises(ValidationError):
            self.act(booking, {"charge_fee": False}, kind="no_show")
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(hours=2)):
            checkout = self.act(booking, {"charge_fee": False}, kind="no_show")
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "no_show")
        self.assertIsNone(checkout.sale)
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertIsNotNone(booking.card_agreement.resolved_at)

    def test_staff_arrival_override_is_separate_from_configured_capacity(self):
        booking = self.booking()
        set_paper(
            actor=self.staff,
            booking_id=booking.pk,
            revision=booking.waiver_review.revision,
            signed=True,
        )
        with self.assertRaises(ValidationError):
            self.act(booking, self.arrival_inputs(booking, children=36, method="cash"))
        self.act(
            booking,
            self.arrival_inputs(booking, children=36, method="cash", override_capacity=True),
        )
        booking.session.refresh_from_db()
        self.assertEqual(booking.session.child_capacity, 35)
        booking.refresh_from_db()
        self.assertEqual(booking.children, 36)

    def test_owner_can_reopen_only_booking_blocks_while_cancelling_without_erasing_manual_closure(
        self,
    ):
        from core.models import Session
        from core.session_blocks import close_for_booking

        booking = self.booking()
        close_for_booking(self.owner, booking)
        Session.objects.filter(pk=booking.session_id).update(closed=True)
        data = {"charge_fee": False, "reopen_affected_sessions": True}
        checked = preview(actor=self.owner, booking_id=booking.pk, kind="cancellation", data=data)
        confirm(
            actor=self.owner,
            booking_id=booking.pk,
            kind="cancellation",
            data=data,
            request_key=uuid.uuid4(),
            reviewed_hash=checked[-1],
            confirmed=True,
        )
        booking.refresh_from_db()
        booking.session.refresh_from_db()
        self.assertEqual(booking.attendance, "cancelled")
        self.assertFalse(booking.session_blocks.filter(active=True).exists())
        self.assertTrue(booking.session.closed)
        self.assertFalse(FinancialPosting.objects.exists())

    def test_staff_cannot_forge_reopening_choice(self):
        from django.core.exceptions import PermissionDenied

        booking = self.booking()
        with self.assertRaises(PermissionDenied):
            preview(
                actor=self.staff,
                booking_id=booking.pk,
                kind="cancellation",
                data={"charge_fee": False, "reopen_affected_sessions": True},
            )
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "")
