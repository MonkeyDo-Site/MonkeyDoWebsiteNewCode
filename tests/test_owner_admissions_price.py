"""Special admissions totals stay fixed on count edits, with optional owner adjustment."""

import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse

from core.booking_estimates import edit_estimate
from core.booking_management import edit_test_booking
from core.models import OwnerNotice
from core.payments.checkout import preview
from core.payments.comped import set_price
from tests import test_booking_checkout as fixtures
from tests.helpers import verified_owner_login


@override_settings(
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
)
class OwnerAdmissionsPriceTests(TestCase):
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

    def priced(self):
        booking = self.booking(children=3)
        set_price(
            actor=self.owner,
            booking_id=booking.pk,
            version=booking.edit_version,
            comped=False,
            special_admissions="40.00",
        )
        booking.refresh_from_db()
        return booking

    def test_socks_are_separate_and_fewer_children_do_not_add_partial_cancellation_fee(self):
        booking = self.priced()
        reviewed = preview(
            actor=self.staff,
            booking_id=booking.pk,
            kind="arrival",
            data=self.arrival_inputs(booking, children=2, socks=2, method="cash"),
        )
        quote = reviewed[2]
        self.assertEqual(quote["subtotal"], "43.98")
        self.assertEqual(quote["lines"][0]["amount"], "40.00")
        self.assertEqual(quote["lines"][1]["label"], "Grip socks — pick up upon arrival")
        self.assertNotIn("Partial cancellation fee", [row["label"] for row in quote["lines"]])
        self.assertEqual(reviewed[4]["fee_units"], 0)
        result = self.act(booking, self.arrival_inputs(booking, children=2, socks=2, method="cash"))
        self.assertEqual(
            result.sale.lines.get(category="owner_priced_admissions").net, Decimal("40")
        )
        self.assertEqual(OwnerNotice.objects.get().details["kind"], "special_price_headcount")

    def test_owner_can_preview_then_explicitly_confirm_a_different_admissions_total(self):
        booking = self.priced()
        values = self.arrival_inputs(
            booking, children=2, special_admissions=Decimal("30"), method="cash"
        )
        reviewed = preview(actor=self.owner, booking_id=booking.pk, kind="arrival", data=values)
        self.assertEqual(reviewed[2]["subtotal"], "30.00")
        booking.charge_state.refresh_from_db()
        self.assertEqual(booking.charge_state.special_subtotal, Decimal("40"))
        from core.payments.checkout import confirm

        result = confirm(
            actor=self.owner,
            booking_id=booking.pk,
            kind="arrival",
            data=values,
            request_key=uuid.uuid4(),
            reviewed_hash=reviewed[-1],
            confirmed=True,
        )
        self.assertEqual(result.sale.subtotal, Decimal("30"))
        booking.charge_state.refresh_from_db()
        self.assertEqual(booking.charge_state.special_subtotal, Decimal("30"))
        self.assertEqual(booking.charge_state.pending_fee_units, 0)

    def test_staff_can_edit_counts_while_retaining_special_price_and_can_not_adjust_price(self):
        booking = self.priced()
        values = dict(
            version=booking.edit_version,
            session=booking.session,
            children=2,
            adults=1,
            babies=0,
            socks=0,
            supervised=False,
            expected_method="cash",
        )
        estimate = edit_estimate(booking, values)
        self.assertEqual(estimate["quote"]["subtotal"], "40.00")
        edit_test_booking(actor=self.staff, booking_id=booking.pk, **values)
        booking.refresh_from_db()
        self.assertEqual(booking.quotes.first().snapshot["subtotal"], "40.00")
        self.assertEqual(booking.charge_state.pending_fee_units, 0)
        with self.assertRaises(PermissionDenied):
            edit_test_booking(
                actor=self.staff,
                booking_id=booking.pk,
                **(values | {"version": booking.edit_version, "special_admissions": Decimal("25")}),
            )
        with self.assertRaises(PermissionDenied):
            preview(
                actor=self.staff,
                booking_id=booking.pk,
                kind="arrival",
                data=self.arrival_inputs(booking, special_admissions=Decimal("25")),
            )

    def test_owner_edit_estimate_and_saved_price_use_same_override_and_tax_basis(self):
        booking = self.priced()
        values = dict(
            version=booking.edit_version,
            session=booking.session,
            children=2,
            adults=1,
            babies=0,
            socks=2,
            supervised=False,
            expected_method="cash",
            special_admissions=Decimal("32"),
        )
        estimate = edit_estimate(booking, values)
        self.assertEqual(estimate["quote"]["subtotal"], "35.98")
        edit_test_booking(actor=self.owner, booking_id=booking.pk, **values)
        self.assertEqual(booking.quotes.first().snapshot["total"], estimate["quote"]["total"])

    def test_staff_cannot_create_a_special_price(self):
        booking = self.booking()
        with self.assertRaises(PermissionDenied):
            set_price(
                actor=self.staff,
                booking_id=booking.pk,
                version=booking.edit_version,
                comped=False,
                special_admissions="5",
            )

    def test_owner_review_keeps_count_notice_and_audits_the_booking_reference(self):
        from core.models import AuditEvent

        booking = self.priced()
        self.act(booking, self.arrival_inputs(booking, children=2, method="cash"))
        notice = OwnerNotice.objects.get()
        verified_owner_login(self.client, self.owner)
        response = self.client.post(reverse("review_notice", args=[notice.pk]))
        self.assertEqual(response.status_code, 302)
        notice.refresh_from_db()
        self.assertIsNotNone(notice.reviewed_at)
        event = AuditEvent.objects.get(action="booking.special_price_notice_reviewed")
        self.assertEqual(event.record_type, "booking")
        self.assertEqual(event.record_id, str(booking.reference))
