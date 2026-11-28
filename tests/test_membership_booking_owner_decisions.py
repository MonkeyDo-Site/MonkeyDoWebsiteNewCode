"""Owner exceptions are explicit, audited and confined to one booking."""

import uuid
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings

from core.booking_estimates import edit_estimate
from core.booking_forms import TestBookingForm
from core.booking_management import edit_test_booking
from core.membership_records import MembershipBookingDecision
from core.membership_reservations import payment_current
from core.models import BookingChargeState, BookingQuote, FinancialSale, PaymentOperation
from core.payments.checkout import confirm, preview, summary
from core.payments.checkout_views import ArrivalForm, confirm_label
from core.payments.comped import set_price
from tests import test_member_booking_integration as fixtures
from tests.test_owner_accounts import STORAGES
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
    BANQUEST_TOKENIZATION_PUBLIC_KEY="pk_fake",
)
class MembershipBookingOwnerTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MemberBookingIntegrationTests.setUp
    flow = fixtures.MemberBookingIntegrationTests.flow
    card = fixtures.MemberBookingIntegrationTests.card
    save_card = fixtures.MemberBookingIntegrationTests.save_card
    booking = fixtures.MemberBookingIntegrationTests.booking
    arrival_inputs = fixtures.MemberBookingIntegrationTests.arrival_inputs
    create = fixtures.MemberBookingIntegrationTests.create
    gateway = fixtures.MemberBookingIntegrationTests.gateway
    ready = fixtures.MemberBookingIntegrationTests.ready
    member = fixtures.MemberBookingIntegrationTests.member

    @contextmanager
    def overdue(self, children=1):
        member = self.member(places=children, billing="monthly")
        booking = self.booking(children=children)
        with patch(
            "core.membership_reservations.today",
            return_value=booking.quotes.first().created_at.date() + timedelta(days=35),
        ):
            self.assertFalse(payment_current(member))
            yield member, booking

    def chosen(self, booking, mode="honor", **changes):
        return self.arrival_inputs(
            booking,
            method="cash",
            membership_resolution=mode,
            membership_resolution_reason="Owner approved this booking after reviewing the installment.",
            **changes,
        )

    def complete(self, booking, data):
        reviewed = preview(actor=self.owner, booking_id=booking.pk, kind="arrival", data=data)
        return confirm(
            actor=self.owner,
            booking_id=booking.pk,
            kind="arrival",
            data=data,
            reviewed_hash=reviewed[-1],
            request_key=uuid.uuid4(),
            confirmed=True,
        )

    def edit_values(self, booking, **changes):
        return (
            dict(
                version=booking.edit_version,
                session=booking.session,
                children=booking.children,
                adults=booking.adults,
                babies=booking.babies,
                socks=booking.socks,
                supervised=booking.supervised,
                expected_method="cash",
            )
            | changes
        )

    def test_preview_is_read_only_owner_must_choose_and_staff_cannot_grant(self):
        with self.overdue() as (_, booking):
            quote = booking.quotes.first()
            with self.assertRaises(ValidationError):
                preview(
                    actor=self.owner,
                    booking_id=booking.pk,
                    kind="arrival",
                    data=self.arrival_inputs(booking),
                )
            with self.assertRaises(PermissionDenied):
                preview(
                    actor=self.staff,
                    booking_id=booking.pk,
                    kind="arrival",
                    data=self.chosen(booking),
                )
            for reason in ("", "x" * 241):
                with self.assertRaises(ValidationError):
                    preview(
                        actor=self.owner,
                        booking_id=booking.pk,
                        kind="arrival",
                        data=self.chosen(booking) | {"membership_resolution_reason": reason},
                    )
            reviewed = preview(
                actor=self.owner, booking_id=booking.pk, kind="arrival", data=self.chosen(booking)
            )
            self.assertEqual(reviewed[2]["total"], "0.00")
            self.assertFalse(MembershipBookingDecision.objects.exists())
            self.assertEqual(booking.quotes.first().pk, quote.pk)
            self.assertEqual(booking.membership_benefits.get().current.status, "reserved")

    def test_honor_one_booking_uses_normal_quota_without_settling_dues_or_granting_other_bookings(
        self,
    ):
        with self.overdue() as (member, booking):
            result = self.complete(booking, self.chosen(booking))
            self.assertIsNone(result.sale)
            booking.refresh_from_db()
            decision = MembershipBookingDecision.objects.get()
            self.assertEqual(decision.memberships, [member.pk])
            self.assertEqual(decision.actor, self.owner)
            self.assertEqual(booking.charge_state.membership_decision, decision)
            self.assertEqual(booking.membership_benefits.filter(current__status="used").count(), 1)
            self.assertFalse(payment_current(member))
            other = self.booking()
            self.assertEqual(other.quotes.first().snapshot["subtotal"], "15.00")
            self.assertFalse(other.membership_benefits.exists())
            self.assertFalse(FinancialSale.objects.filter(booking=booking).exists())

    def test_honored_benefits_keep_partial_cancellation_fee_and_release_absent_place(self):
        with self.overdue(children=2) as (_, booking):
            result = self.complete(booking, self.chosen(booking, children=1))
            self.assertEqual(result.sale.total, Decimal("3.00"))
            self.assertEqual(
                result.sale.lines.get(category="partial_cancellation").net, Decimal("3.00")
            )
            booking.refresh_from_db()
            self.assertEqual(booking.membership_benefits.filter(current__status="used").count(), 1)
            self.assertEqual(summary(booking)["received"], Decimal("3.00"))

    def test_ordinary_pricing_releases_benefits_and_charges_actual_standard_amount(self):
        with self.overdue() as (_, booking):
            result = self.complete(booking, self.chosen(booking, "ordinary"))
            self.assertEqual(result.sale.subtotal, Decimal("15.00"))
            self.assertEqual(result.sale.sales_tax, Decimal("0.99"))
            self.assertEqual(booking.membership_benefits.get().current.status, "released")
            self.assertEqual(MembershipBookingDecision.objects.get().mode, "ordinary")

    def test_edit_estimate_and_save_share_decision_then_staff_can_use_it_only_on_this_session(self):
        with self.overdue() as (_, booking):
            values = self.edit_values(
                booking,
                membership_resolution="honor",
                membership_resolution_reason="Owner approved this visit.",
            )
            estimate = edit_estimate(booking, values, actor=self.owner)
            self.assertEqual(estimate["quote"]["total"], "0.00")
            self.assertFalse(MembershipBookingDecision.objects.exists())
            edit_test_booking(actor=self.owner, booking_id=booking.pk, **values)
            booking.refresh_from_db()
            self.assertEqual(booking.quotes.first().snapshot["total"], "0.00")
            allowed = preview(
                actor=self.staff,
                booking_id=booking.pk,
                kind="arrival",
                data=self.arrival_inputs(booking),
            )
            self.assertEqual(allowed[2]["total"], "0.00")
            later = self.create(
                starts_at=booking.session.starts_at + timedelta(days=1),
                ends_at=booking.session.ends_at + timedelta(days=1),
            )
            with self.assertRaises(ValidationError):
                edit_test_booking(
                    actor=self.staff,
                    booking_id=booking.pk,
                    **self.edit_values(booking, session=later),
                )
            booking.refresh_from_db()
            self.assertNotEqual(booking.session_id, later.pk)

    def test_ordinary_decision_recalculates_counts_instead_of_fixing_an_admissions_price(self):
        with self.overdue() as (_, booking):
            values = self.edit_values(
                booking,
                membership_resolution="ordinary",
                membership_resolution_reason="Use ordinary prices.",
            )
            edit_test_booking(actor=self.owner, booking_id=booking.pk, **values)
            booking.refresh_from_db()
            self.assertIsNone(booking.charge_state.special_subtotal)
            edit_test_booking(
                actor=self.staff, booking_id=booking.pk, **self.edit_values(booking, children=2)
            )
            booking.refresh_from_db()
            self.assertEqual(booking.quotes.first().snapshot["subtotal"], "30.00")
            self.assertFalse(
                booking.membership_benefits.filter(current__status="reserved").exists()
            )

    def test_stale_review_or_removed_waiver_confirmation_cannot_record_an_exception(self):
        with self.overdue() as (_, booking):
            values = self.chosen(booking)
            digest = preview(actor=self.owner, booking_id=booking.pk, kind="arrival", data=values)[
                -1
            ]
            with self.assertRaises(ValidationError):
                confirm(
                    actor=self.owner,
                    booking_id=booking.pk,
                    kind="arrival",
                    data=values | {"membership_resolution_reason": "Changed reason"},
                    request_key=uuid.uuid4(),
                    reviewed_hash=digest,
                    confirmed=True,
                )
            with self.assertRaises(ValidationError):
                self.complete(booking, values | {"waiver_confirmed": False})
            self.assertFalse(MembershipBookingDecision.objects.exists())

    def test_owner_controls_only_appear_for_affected_bookings_and_owner(self):
        booking = self.booking()
        self.assertNotIn("membership_resolution", ArrivalForm(booking=booking, owner=True).fields)
        with self.overdue() as (_, affected):
            for factory in (ArrivalForm, TestBookingForm):
                self.assertIn("membership_resolution", factory(booking=affected, owner=True).fields)
                self.assertNotIn(
                    "membership_resolution", factory(booking=affected, owner=False).fields
                )

    def test_owner_exception_does_not_bypass_capacity(self):
        with self.overdue() as (_, booking):
            with self.assertRaises(ValidationError):
                self.complete(booking, self.chosen(booking, children=32767))
            self.assertFalse(MembershipBookingDecision.objects.exists())

    def test_honor_cannot_extend_the_membership_term_to_a_later_session(self):
        with self.overdue() as (_, booking):
            later = self.create(
                starts_at=booking.session.starts_at + timedelta(days=100),
                ends_at=booking.session.ends_at + timedelta(days=100),
            )
            values = self.edit_values(
                booking,
                session=later,
                membership_resolution="honor",
                membership_resolution_reason="One booking only.",
            )
            with self.assertRaises(ValidationError):
                edit_estimate(booking, values, actor=self.owner)
            with self.assertRaises(ValidationError):
                edit_test_booking(actor=self.owner, booking_id=booking.pk, **values)
            self.assertFalse(MembershipBookingDecision.objects.exists())

    def test_database_rejects_an_exception_attributed_to_ordinary_staff(self):
        with self.overdue() as (_, booking):
            with self.runtime_role(), self.assertRaises(DatabaseError), transaction.atomic():
                MembershipBookingDecision.objects.create(
                    id=uuid.uuid4(),
                    booking=booking,
                    session=booking.session,
                    mode="ordinary",
                    memberships=[],
                    reason="Staff cannot grant this.",
                    actor=self.staff,
                )

    def test_quote_metadata_cannot_grant_an_exception_without_the_owner_decision(self):
        from core.membership_reservations import reserve

        with self.overdue() as (_, booking):
            saved = booking.quotes.first()
            reviewed = preview(
                actor=self.owner, booking_id=booking.pk, kind="arrival", data=self.chosen(booking)
            )
            forged = BookingQuote.objects.create(
                booking=booking,
                policy=saved.policy,
                revision=saved.revision + 1,
                snapshot=reviewed[2],
                actor=self.staff,
            )
            with self.assertRaises(ValidationError):
                reserve(
                    actor=self.staff,
                    booking_id=booking.pk,
                    quote_id=forged.pk,
                    request_key=uuid.uuid4(),
                )
            self.assertFalse(MembershipBookingDecision.objects.exists())
            self.assertEqual(
                booking.membership_benefits.filter(current__status="reserved").count(), 1
            )

    def test_runtime_evidence_is_immutable_and_projection_cannot_point_to_another_booking(self):
        with self.overdue() as (_, booking):
            with self.runtime_role():
                self.complete(booking, self.chosen(booking))
            decision = MembershipBookingDecision.objects.get()
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE core_membershipbookingdecision SET mode='ordinary' WHERE id=%s",
                        [decision.pk],
                    )
            other = self.booking()
            with self.assertRaises(DatabaseError), transaction.atomic():
                BookingChargeState.objects.create(booking=other, membership_decision=decision)

    def test_custom_zero_admissions_is_not_a_complimentary_booking_or_membership_use(self):
        booking = self.booking()
        set_price(
            actor=self.owner,
            booking_id=booking.pk,
            version=booking.edit_version,
            comped=False,
            special_admissions="0.00",
        )
        booking.refresh_from_db()
        values = self.arrival_inputs(booking, method="cash")
        reviewed = preview(actor=self.staff, booking_id=booking.pk, kind="arrival", data=values)
        self.assertEqual(
            confirm_label("arrival", reviewed[2], reviewed[3]), "Confirm arrival — no payment due"
        )
        result = confirm(
            actor=self.staff,
            booking_id=booking.pk,
            kind="arrival",
            data=values,
            request_key=uuid.uuid4(),
            reviewed_hash=reviewed[-1],
            confirmed=True,
        )
        self.assertIsNone(result.sale)
        booking.refresh_from_db()
        self.assertFalse(booking.charge_state.comped)
        self.assertEqual(summary(booking)["status"], "No payment due")
        self.assertFalse(PaymentOperation.objects.filter(sale__booking=booking).exists())

    def cancel_member(self, member):
        from core.membership_cancellations import cancel, review

        data = review(
            actor=self.owner, member_id=member.pk, timing="immediate", refund_amount="0.00"
        )
        return cancel(
            actor=self.owner,
            member_id=member.pk,
            timing="immediate",
            refund_amount="0.00",
            reviewed=data["fingerprint"],
            request_key=uuid.uuid4(),
            reason="Owner approved cancellation and will review the existing booking.",
            early_override=True,
            send_confirmation=False,
        )

    def test_membership_cancellation_preserves_future_booking_and_price_until_explicit_owner_review(
        self,
    ):
        from core.membership_cancellations import notices

        member = self.member()
        booking = self.booking()
        saved = booking.quotes.first()
        self.cancel_member(member)
        self.assertEqual(notices()["affected"][0].affected_count, 1)
        with self.assertRaisesMessage(ValidationError, "has not been repriced"):
            preview(
                actor=self.staff,
                booking_id=booking.pk,
                kind="arrival",
                data=self.arrival_inputs(booking),
            )
        with self.assertRaises(ValidationError):
            self.complete(booking, self.chosen(booking))
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "")
        self.assertEqual(booking.quotes.first().pk, saved.pk)
        self.assertEqual(booking.membership_benefits.get().current.status, "reserved")
        result = self.complete(booking, self.chosen(booking, "ordinary"))
        self.assertEqual(result.sale.total, Decimal("15.99"))
        self.assertFalse(notices()["affected"])
        self.assertEqual(booking.membership_benefits.get().current.status, "released")

    def test_prior_honor_decision_cannot_keep_using_a_later_cancelled_membership(self):
        with self.overdue() as (member, booking):
            edit_test_booking(
                actor=self.owner,
                booking_id=booking.pk,
                **self.edit_values(
                    booking,
                    membership_resolution="honor",
                    membership_resolution_reason="Honor existing benefits.",
                ),
            )
            self.cancel_member(member)
            booking.refresh_from_db()
            with self.assertRaisesMessage(ValidationError, "has not been repriced"):
                preview(
                    actor=self.staff,
                    booking_id=booking.pk,
                    kind="arrival",
                    data=self.arrival_inputs(booking),
                )
            self.assertEqual(booking.quotes.first().snapshot["total"], "0.00")
