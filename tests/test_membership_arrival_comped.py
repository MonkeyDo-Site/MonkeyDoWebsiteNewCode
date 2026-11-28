"""A paid membership does not remove the owner's complimentary visit decision."""

from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.communications.models import MessageDelivery
from core.membership_arrival import confirm, receipt_summary, review
from core.membership_arrival_pending import complete
from core.membership_records import (
    MembershipArrivalCheckout,
    MembershipArrivalIntent,
    MembershipPurchase,
)
from core.models import FinancialPosting, FinancialSale, PaymentOperation
from core.payments.comped import set_comped
from core.payments.ledger import record_result
from core.payments.staff_setup import session_key
from tests import test_membership_arrival as arrivals
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class CompedVisitMembershipTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = arrivals.CombinedMembershipArrivalTests.prepare
    web_data = arrivals.CombinedMembershipArrivalTests.web_data

    def comped_visit(self, *, booking=None, **changes):
        booking = booking or self.prepare(**changes)
        set_comped(
            actor=self.owner, booking_id=booking.pk, version=booking.edit_version, comped=True
        )
        booking.refresh_from_db()
        self.client.force_login(self.staff)
        url = reverse("staff_booking_setup", args=[booking.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        flow = self.client.session[session_key(booking.pk)]
        result = self.client.post(
            url, {"wizard_key": flow["key"], "waiver_type": "single", "confirm": "on"}
        )
        self.assertEqual(result.status_code, 302, result.content)
        booking.refresh_from_db()
        self.assertFalse(booking.setup_pending)
        return booking

    def test_reconfirming_comped_setup_preserves_original_email_and_queues_current_version_once(
        self,
    ):
        booking = self.prepare()
        original = MessageDelivery.objects.get(dedupe_key=f"booking-confirmation:{booking.pk}")
        fingerprint, text = original.fingerprint, original.text_body
        booking = self.comped_visit(booking=booking)
        current = MessageDelivery.objects.get(
            dedupe_key=f"booking-setup-confirmation:{booking.pk}:{booking.edit_version}"
        )
        original.refresh_from_db()
        self.assertEqual((original.fingerprint, original.text_body), (fingerprint, text))
        self.assertNotEqual(current.fingerprint, original.fingerprint)
        self.assertNotIn("Cancellation fees will apply", current.text_body)
        url = reverse("staff_booking_setup", args=[booking.pk])
        count = MessageDelivery.objects.count()
        self.assertEqual(self.client.post(url, {}).status_code, 302)
        self.assertEqual(MessageDelivery.objects.count(), count)
        self.assertFalse(PaymentOperation.objects.exists())

    def commit_comped(self, **changes):
        return confirm(
            **(
                self.options
                | dict(
                    request_key=self.key,
                    reviewed_hash=review(**self.options)["fingerprint"],
                    confirmed=True,
                    accepted=True,
                    verified_received=True,
                )
                | changes
            )
        )

    def test_cash_purchase_records_only_membership_and_preserves_comped_unused_visit(self):
        booking = self.comped_visit(method="cash")
        reviewed = review(**self.options)
        self.assertEqual(reviewed["facts"]["visit_due"], "0.00")
        self.assertEqual(reviewed["facts"]["received_today"], "35.98")
        self.assertEqual(reviewed["plan"], [])
        self.assertFalse(MembershipPurchase.objects.exists())
        with self.runtime_role(), patch("core.payments.operations.Gateway") as gateway:
            record = self.commit_comped()
            again = confirm(
                **self.options,
                request_key=self.key,
                reviewed_hash=record.fingerprint,
                confirmed=True,
                accepted=True,
                verified_received=True,
            )
            self.assertEqual(again.pk, record.pk)
            gateway.assert_not_called()
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "arrived")
        self.assertTrue(booking.charge_state.comped)
        self.assertFalse(booking.membership_benefits.exists())
        self.assertIsNone(record.checkout.sale_id)
        self.assertFalse(FinancialSale.objects.filter(booking=booking).exists())
        operation = PaymentOperation.objects.get()
        self.assertEqual((operation.tender, operation.amount), ("cash", Decimal("35.98")))
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("35.98"))
        self.assertEqual(receipt_summary(record)["visit_received"], Decimal("0.00"))
        self.assertIsNotNone(record.purchase.billing_state.mandate_id)
        mail = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("Visit payment received: $0.00", mail.text_body)

    def test_prepaid_verified_gift_needs_no_future_card_or_visit_receipt(self):
        booking = self.comped_visit(method="gift_card", billing="prepaid")
        self.options["data"]["gift_card_verified"] = True
        record = self.commit_comped(verified_received=False)
        self.assertIsNone(record.purchase.billing_state.mandate_id)
        self.assertIsNone(record.checkout.sale_id)
        self.assertFalse(booking.membership_benefits.exists())
        operation = PaymentOperation.objects.get()
        self.assertEqual((operation.tender, operation.amount), ("gift_card", Decimal("107.94")))

    def test_card_funding_completes_only_comped_arrival_without_a_second_payment(self):
        booking = self.comped_visit(method="card")
        self.options["method_id"] = booking.card_agreement.method_id
        with self.runtime_role():
            intent = self.commit_comped(verified_received=False)
            self.assertIsInstance(intent, MembershipArrivalIntent)
            self.assertEqual(intent.operation.amount, Decimal("37.06"))
            booking.refresh_from_db()
            self.assertEqual(booking.attendance, "")
            self.assertFalse(MembershipArrivalCheckout.objects.exists())
            record_result(
                operation_id=intent.operation_id,
                state="succeeded",
                source="provider",
                provider_reference="993",
            )
            self.assertEqual(complete(intent.pk).status, "completed")
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "arrived")
        self.assertTrue(booking.charge_state.comped)
        self.assertFalse(booking.membership_benefits.exists())
        self.assertEqual(PaymentOperation.objects.count(), 1)
        record = MembershipArrivalCheckout.objects.get(pk=intent.pk)
        self.assertIsNone(record.checkout.sale_id)
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("37.06"))

    def test_one_page_uses_membership_tender_only_after_explicit_purchase_selection(self):
        booking = self.comped_visit()
        url = reverse("booking_arrival", args=[booking.pk])
        page = self.client.get(url)
        self.assertEqual(
            list(page.context["form"].fields["method"].choices),
            [("comped", "Owner-comped booking — no payment")],
        )
        self.assertContains(page, "data-comped-membership-methods")
        values = self.web_data(booking) | {"arrival_draft": page.context["arrival_draft"]}
        native = self.client.post(url, values)
        self.assertContains(native, "Membership payment (visit is owner-comped)")
        self.assertContains(native, "The visit stays owner-comped at $0")
        choices = dict(native.context["form"].fields["method"].choices)
        self.assertEqual(set(choices), {"", "cash", "check", "card", "gift_card"})
        quote = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(quote.status_code, 200, quote.content)
        self.assertTrue(quote.json()["can_confirm"])
        self.assertIn("record cash $35.98", quote.json()["label"])
        self.assertEqual(quote.json()["membership_card_purchase"]["expected_method"], "cash")
        self.assertFalse(PaymentOperation.objects.exists())
        response = self.client.post(
            url,
            values | {"confirm_review": "1", "reviewed_hash": quote.json()["hash"]},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["confirmed"])
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_ordinary_comped_arrival_cannot_select_paid_tender_without_a_membership(self):
        booking = self.comped_visit()
        url = reverse("booking_arrival", args=[booking.pk])
        page = self.client.get(url)
        values = self.web_data(booking) | {"arrival_draft": page.context["arrival_draft"]}
        values.pop("member_add")
        result = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(result.status_code, 400)
        self.assertIn("method", result.json()["errors"])
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(MembershipPurchase.objects.exists())

    def test_disabled_membership_feature_keeps_original_comped_only_control(self):
        booking = self.comped_visit()
        with override_settings(MEMBERSHIP_SALES_ENABLED=False):
            page = self.client.get(reverse("booking_arrival", args=[booking.pk]))
        self.assertNotContains(page, "data-comped-membership-methods")
        self.assertNotIn("member_add", page.context["form"].fields)
        self.assertEqual(list(page.context["form"].fields["method"].choices)[0][0], "comped")

    def test_waiver_and_current_owner_decision_are_still_required_before_payment(self):
        booking = self.comped_visit()
        self.options["data"]["waiver_confirmed"] = False
        with self.assertRaisesMessage(ValidationError, "waiver"):
            self.commit_comped()
        self.options["data"]["waiver_confirmed"] = True
        reviewed = review(**self.options)
        set_comped(
            actor=self.owner, booking_id=booking.pk, version=booking.edit_version, comped=False
        )
        with self.assertRaises(ValidationError):
            self.commit_comped(reviewed_hash=reviewed["fingerprint"])
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_late_failure_rolls_back_membership_and_keeps_the_owner_comped_booking(self):
        booking = self.comped_visit()
        with (
            patch(
                "core.membership_arrival.queue_confirmation",
                side_effect=ValidationError("late fault"),
            ),
            self.assertRaisesMessage(ValidationError, "late fault"),
        ):
            self.commit_comped()
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "")
        self.assertTrue(booking.charge_state.comped)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())
