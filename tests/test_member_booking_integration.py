"""Member pricing follows the real public/staff booking and arrival boundaries."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.availability import NEW_YORK
from core.booking_management import edit_test_booking, move_test_booking
from core.membership_records import MembershipBenefitAssignment
from core.membership_sales import offer, purchase
from core.models import Booking, FinancialSale, PaymentMethod, PaymentOperation, Session
from core.payments.checkout import preview, summary
from core.payments.checkout_views import confirm_label
from core.payments.comped import set_price
from core.public_booking import review_quote, submit_booking
from core.waivers.services import approved_version, sign
from tests import test_booking_checkout as checkout
from tests import test_single_page_staff_booking as staff_fixtures
from tests.test_owner_accounts import STORAGES
from tests.test_waivers import MemoryEvidence


@override_settings(
    STORAGES=STORAGES,
    MEMBERSHIP_SALES_ENABLED=True,
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
    BANQUEST_TOKENIZATION_PUBLIC_KEY="pk_fake_sandbox",
)
class MemberBookingIntegrationTests(TestCase):
    setUp = checkout.CheckoutTests.setUp
    flow = checkout.CheckoutTests.flow
    card = checkout.CheckoutTests.card
    save_card = checkout.CheckoutTests.save_card
    booking = checkout.CheckoutTests.booking
    arrival_inputs = checkout.CheckoutTests.arrival_inputs
    act = checkout.CheckoutTests.act
    draft = staff_fixtures.SinglePageStaffBookingTests.draft
    post = staff_fixtures.SinglePageStaffBookingTests.post
    staff_save_card = staff_fixtures.SinglePageStaffBookingTests.save_card

    def create(self, **changes):
        start = (self.data | changes)["starts_at"]
        return Session.objects.filter(starts_at=start).first() or checkout.CheckoutTests.create(
            self, **changes
        )

    def gateway(self, mocked):
        reference = uuid.uuid4().int % 1000000000 + 1
        mocked.return_value.create_customer.return_value = {"id": 12}
        mocked.return_value.save_card.return_value = {"id": reference}
        mocked.return_value.method.return_value = self.card() | {"id": reference}

    def ready(self):
        flow = self.flow()
        flow["session_id"] = self.create().pk
        flow["details"] = dict(
            children=1, adults=1, babies=0, socks=0, supervised=False, expected_method="card"
        )
        flow["quote"] = review_quote(flow, flow["details"])
        version = approved_version()
        with patch("core.waivers.services.EvidenceStore", return_value=MemoryEvidence()):
            signed = sign(
                data=dict(
                    request_key=uuid.uuid4(),
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
        flow["waiver_signatures"] = [str(signed.pk)]
        flow["waiver_coverage"] = True
        with patch("core.payments.setup.Gateway") as gateway:
            self.gateway(gateway)
            setup = self.save_card(flow)
        flow["payment_consent"] = str(setup.consent_id)
        return flow

    def member(self, *, places=1, kind="subscription", billing="prepaid"):
        values = dict(
            actor=self.staff,
            customer=self.customer,
            kind=kind,
            places=places,
            months=3,
            billing=billing,
            starts_on=timezone.localdate(timezone=NEW_YORK),
            expected_method="cash",
        )
        method = None
        if billing == "monthly":
            method = PaymentMethod.objects.create(
                customer=self.customer,
                provider_customer="12",
                provider_method="9999999999",
                brand="Visa",
                last_four="1118",
                reusable=True,
                consent_version="MD-PAYMENT-2026-05",
                consent_at=timezone.now(),
            )
        return purchase(
            **values,
            request_key=uuid.uuid4(),
            reviewed=offer(**values)["fingerprint"],
            accepted=True,
            verified_received=True,
            method_id=method.pk if method else None,
        )

    def test_public_preview_and_card_saving_do_not_reserve_benefits_but_confirmation_does(self):
        self.member()
        flow = self.ready()
        self.assertEqual(flow["quote"]["total"], "0.00")
        self.assertFalse(MembershipBenefitAssignment.objects.exists())
        booking = submit_booking(flow)
        self.assertEqual(booking.membership_benefits.get().kind, "subscription_free")
        self.assertFalse(booking.setup_pending)
        self.assertFalse(PaymentOperation.objects.filter(sale__booking=booking).exists())
        self.assertEqual(submit_booking(flow).pk, booking.pk)
        self.assertEqual(booking.membership_benefits.count(), 1)

    def test_zero_due_member_arrival_records_usage_without_fabricating_payment_or_comping(self):
        self.member()
        booking = self.booking()
        data = self.arrival_inputs(booking)
        reviewed = preview(actor=self.staff, booking_id=booking.pk, kind="arrival", data=data)
        self.assertEqual(reviewed[2]["total"], "0.00")
        self.assertEqual(reviewed[3], [])
        self.assertEqual(
            confirm_label("arrival", reviewed[2], reviewed[3]), "Confirm arrival — no payment due"
        )
        result = self.act(booking, data)
        self.assertIsNone(result.sale)
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "arrived")
        self.assertFalse(booking.charge_state.comped)
        self.assertEqual(booking.membership_benefits.filter(current__status="used").count(), 1)
        self.assertEqual(summary(booking)["status"], "Covered by membership")
        self.assertFalse(FinancialSale.objects.filter(booking=booking).exists())
        self.assertEqual(summary(booking)["total_received"], Decimal("0.00"))

    def test_partial_removal_of_free_member_admission_keeps_three_dollar_fee_and_releases_extra_place(
        self,
    ):
        self.member(places=2)
        booking = self.booking(children=3)
        self.assertEqual(booking.quotes.first().snapshot["subtotal"], "15.00")
        data = self.arrival_inputs(booking, children=2, method="cash")
        reviewed = preview(actor=self.staff, booking_id=booking.pk, kind="arrival", data=data)
        self.assertEqual(reviewed[2]["total"], "3.00")
        result = self.act(booking, data)
        self.assertEqual(result.sale.total, Decimal("3.00"))
        self.assertEqual(
            result.sale.lines.get(category="partial_cancellation").net, Decimal("3.00")
        )
        self.assertEqual(
            result.sale.lines.get(category="partial_cancellation").item_tax, Decimal("0.00")
        )
        self.assertEqual(booking.membership_benefits.filter(current__status="used").count(), 2)

    def test_cancelling_free_visit_releases_benefit_and_collects_cancellation_fee(self):
        self.member()
        booking = self.booking()
        result = self.act(booking, dict(method="card", charge_fee=True), kind="cancellation")
        self.assertEqual(result.sale.total, Decimal("3.09"))
        self.assertEqual(booking.membership_benefits.get().current.status, "released")
        self.assertEqual(result.sale.operations.get().purpose, "cancellation")

    def test_overdue_installment_does_not_silently_reprice_existing_booking(self):
        self.member(billing="monthly")
        booking = self.booking()
        old = booking.quotes.first()
        with patch(
            "core.membership_reservations.today",
            return_value=old.created_at.date() + timedelta(days=35),
        ):
            with self.assertRaisesMessage(ValidationError, "This booking has not been repriced"):
                preview(
                    actor=self.staff,
                    booking_id=booking.pk,
                    kind="arrival",
                    data=self.arrival_inputs(booking),
                )
        booking.refresh_from_db()
        self.assertEqual(booking.quotes.first().pk, old.pk)
        self.assertEqual(booking.membership_benefits.get().current.status, "reserved")
        self.assertEqual(booking.attendance, "")

    def test_released_unlimited_benefit_needs_explicit_apply_on_existing_booking(self):
        self.member(kind="unlimited")
        first = self.booking()
        second = self.booking()
        self.assertFalse(second.quotes.first().snapshot["membership_benefits_applied"])
        self.act(first, dict(method="card", charge_fee=False), kind="cancellation")
        normal = preview(
            actor=self.staff, booking_id=second.pk, kind="arrival", data=self.arrival_inputs(second)
        )
        self.assertEqual(normal[2]["total"], "16.47")
        applied = preview(
            actor=self.staff,
            booking_id=second.pk,
            kind="arrival",
            data=self.arrival_inputs(second, apply_available_benefits=True),
        )
        self.assertEqual(applied[2]["total"], "0.00")
        self.assertFalse(second.membership_benefits.exists())
        self.act(second, self.arrival_inputs(second, apply_available_benefits=True))
        self.assertEqual(second.membership_benefits.filter(current__status="used").count(), 1)

    def test_explicit_member_benefit_can_be_applied_from_edit_without_changing_counts(self):
        self.member(kind="unlimited")
        first, second = self.booking(), self.booking()
        self.act(first, dict(method="card", charge_fee=False), kind="cancellation")
        edit_test_booking(
            actor=self.staff,
            booking_id=second.pk,
            version=second.edit_version,
            children=second.children,
            adults=second.adults,
            babies=second.babies,
            socks=second.socks,
            expected_method=second.expected_method,
            apply_available_benefits=True,
        )
        self.assertEqual(second.quotes.first().snapshot["total"], "0.00")
        self.assertEqual(second.membership_benefits.get().current.status, "reserved")

    def test_timing_change_releases_old_cycle_reservation_and_records_new_cycle(self):
        self.member()
        booking = self.booking()
        old = booking.membership_benefits.get()
        target = self.create(
            starts_at=booking.session.starts_at + timedelta(days=35),
            ends_at=booking.session.ends_at + timedelta(days=35),
        )
        move_test_booking(
            actor=self.staff,
            booking_id=booking.pk,
            version=booking.edit_version,
            session_id=target.pk,
        )
        old.refresh_from_db()
        self.assertEqual(old.current.status, "released")
        new = booking.membership_benefits.get(current__status="reserved")
        self.assertNotEqual(new.cycle_id, old.cycle_id)
        self.assertEqual(
            booking.quotes.first().snapshot["membership_appointment_on"],
            target.starts_at.astimezone(NEW_YORK).date().isoformat(),
        )

    def test_owner_comped_booking_never_spends_membership_benefits(self):
        self.member()
        booking = self.booking()
        set_price(
            actor=self.owner, booking_id=booking.pk, version=booking.edit_version, comped=True
        )
        booking.refresh_from_db()
        self.assertFalse(booking.membership_benefits.filter(current__status="reserved").exists())
        Booking.objects.filter(pk=booking.pk).update(setup_pending=False)
        booking.refresh_from_db()
        self.act(booking, self.arrival_inputs(booking, method="comped"))
        self.assertFalse(booking.membership_benefits.filter(current__status="used").exists())
        self.assertEqual(summary(booking)["status"], "Comped")

    def test_single_page_staff_booking_uses_member_price_and_reserves_only_on_final_confirmation(
        self,
    ):
        self.member(places=2)
        self.draft()
        preview_response = self.post("preview", children=3, adults=2)
        self.assertEqual(preview_response.status_code, 200, preview_response.content)
        self.assertIn("$15.99", preview_response.json()["html"])
        self.assertFalse(MembershipBenefitAssignment.objects.exists())
        self.staff_save_card()
        result = self.post("confirm")
        self.assertEqual(result.status_code, 200, result.content)
        booking = Booking.objects.get()
        self.assertEqual(booking.quotes.first().snapshot["subtotal"], "15.00")
        self.assertEqual(booking.membership_benefits.filter(current__status="reserved").count(), 2)
        self.assertFalse(PaymentOperation.objects.filter(sale__booking=booking).exists())

    def test_membership_never_bypasses_configured_session_capacity(self):
        self.member(places=2)
        self.create(
            child_capacity=1, total_capacity=2, supervised_capacity=0, play_mode="accompanied"
        )
        self.booking()
        with self.assertRaises(ValidationError):
            self.ready()
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(
            MembershipBenefitAssignment.objects.filter(current__status="reserved").count(), 1
        )

    def test_subscription_supervised_discount_preserves_ordinary_free_quota(self):
        from core.membership_reservations import summary_for

        member = self.member()
        flow = self.ready()
        flow["details"].update(supervised=True, adults=0)
        flow["quote"] = review_quote(flow, flow["details"])
        self.assertEqual(flow["quote"]["lines"][0]["unit_price"], "14.24")
        booking = submit_booking(flow)
        self.assertEqual(booking.membership_benefits.get().kind, "subscription_supervised")
        self.assertEqual(summary_for(member)["available"], 2)
        result = self.act(booking, self.arrival_inputs(booking, method="cash"))
        self.assertEqual(result.sale.total, Decimal("15.18"))
        self.assertEqual(
            result.sale.lines.get(category="member_subscription_supervised").net, Decimal("14.24")
        )
        self.assertEqual(summary_for(member)["available"], 2)

    def test_member_baby_only_visit_keeps_required_admission_and_no_child_benefit_use(self):
        self.member()
        flow = self.ready()
        flow["details"].update(children=0, babies=1)
        flow["quote"] = review_quote(flow, flow["details"])
        self.assertEqual(flow["quote"]["subtotal"], "15.00")
        booking = submit_booking(flow)
        self.assertFalse(booking.membership_benefits.exists())
        self.assertFalse(booking.quotes.first().snapshot["membership_benefits_applied"])

    def test_comped_membership_still_records_member_usage_instead_of_comping_the_visit(self):
        values = dict(
            actor=self.owner,
            customer=self.customer,
            kind="subscription",
            places=1,
            months=1,
            billing="prepaid",
            starts_on=timezone.localdate(timezone=NEW_YORK),
            expected_method="cash",
            comped=True,
        )
        member = purchase(
            **values,
            request_key=uuid.uuid4(),
            reviewed=offer(**values)["fingerprint"],
            accepted=True,
            send_confirmation=False,
        )
        self.assertFalse(FinancialSale.objects.exists())
        booking = self.booking()
        self.act(booking, self.arrival_inputs(booking))
        booking.refresh_from_db()
        self.assertFalse(booking.charge_state.comped)
        self.assertEqual(
            booking.membership_benefits.get(current__status="used").purchase_id, member.pk
        )
        self.assertEqual(summary(booking)["status"], "Covered by membership")
