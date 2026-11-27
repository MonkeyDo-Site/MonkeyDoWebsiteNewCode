"""Manual membership funding and split visit receipts conserve actual money."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.communications.models import MessageDelivery
from core.membership_arrival import confirm, receipt_summary, review
from core.membership_arrival_forms import ready
from core.membership_records import MembershipPurchase
from core.models import FinancialPosting, PaymentOperation
from core.payments import remainders
from core.payments.invoices import received
from core.payments.ledger import record_result
from core.payments.operations import begin_dispatch, execute
from tests import test_membership_arrival as arrivals
from tests import test_membership_arrival_card as credit_arrivals
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class SplitMembershipArrivalTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = arrivals.CombinedMembershipArrivalTests.prepare
    web_data = arrivals.CombinedMembershipArrivalTests.web_data

    def split_visit(self, *, member="cash", amounts=None, **changes):
        booking = self.prepare(method="split", **changes)
        self.input.update(
            member_first_method=member,
            split={"cash": "10.00"} if amounts is None else amounts,
        )
        return booking

    def confirm_split(self, **changes):
        values = self.options | dict(
            request_key=self.key,
            reviewed_hash=changes.get("reviewed_hash") or review(**self.options)["fingerprint"],
            confirmed=True,
            accepted=True,
            verified_received=True,
        )
        return confirm(**(values | changes))

    def test_cash_membership_visit_cash_and_card_have_exact_separate_amounts_and_one_message(self):
        booking = self.split_visit()
        proposed = review(**self.options)
        self.assertEqual(proposed["facts"]["membership_due"], "35.98")
        self.assertEqual(proposed["facts"]["visit_due"], "16.17")
        self.assertEqual(proposed["facts"]["received_today"], "45.98")
        self.assertEqual(proposed["facts"]["payment_due_today"], "6.17")
        self.assertEqual(proposed["facts"]["total_due_today"], "52.15")
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        with self.runtime_role():
            record = self.confirm_split()
            self.assertEqual(self.confirm_split(reviewed_hash=record.fingerprint).pk, record.pk)
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "arrived")
        self.assertEqual(
            received(record.purchase.installments.first().invoice.sale), Decimal("35.98")
        )
        self.assertEqual(received(record.checkout.sale), 10)
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("45.98"))
        card = record.checkout.sale.operations.get(tender="card")
        self.assertEqual(card.amount, Decimal("6.17"))
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertEqual(record.purchase.installments.get(number=2).quote["total"], "37.06")
        self.assertFalse(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").exists()
        )
        with patch("core.payments.operations.Gateway") as gateway:
            self.assertIsNotNone(begin_dispatch(card.pk))
            gateway.assert_not_called()
        record_result(
            operation_id=card.pk, state="succeeded", source="provider", provider_reference="441001"
        )
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("52.15"))
        mail = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("New payment received: $52.15", mail.text_body)
        self.assertIn("Credit-card processing fee: $0.17", mail.text_body)
        self.assertFalse(MessageDelivery.objects.filter(kind="membership_confirmation").exists())

    def test_cash_and_check_visit_sum_with_membership_without_duplicate_physical_receipts(self):
        self.split_visit(amounts={"cash": "10.00", "check": "5.99"})
        record = self.confirm_split()
        self.assertEqual(
            record.facts["manual_parts"],
            [
                {"method": "cash", "label": "Cash", "amount": "45.98"},
                {"method": "check", "label": "Check", "amount": "5.99"},
            ],
        )
        self.assertNotIn("payment_due_today", record.facts)
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertFalse(PaymentOperation.objects.filter(tender="card").exists())
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("51.97"))
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").count(), 1
        )

    def test_membership_gift_and_visit_gift_share_strict_physical_verification(self):
        self.split_visit(member="gift_card", amounts={"gift_card": "10.00", "cash": "5.99"})
        with self.assertRaisesMessage(ValidationError, "physical gift card"):
            self.confirm_split()
        self.assertFalse(PaymentOperation.objects.exists())
        self.input["gift_card_verified"] = True
        record = self.confirm_split(verified_received=False)
        self.assertIn(
            {"method": "gift_card", "label": "Gift card", "amount": "45.98"},
            record.facts["manual_parts"],
        )
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("51.97"))
        self.assertEqual(PaymentOperation.objects.filter(tender="gift_card").count(), 2)

    def test_unverified_visit_gift_rolls_back_the_separate_check_membership_receipt(self):
        booking = self.split_visit(member="check", amounts={"gift_card": "5.00", "cash": "10.99"})
        with self.assertRaises(ValidationError):
            self.confirm_split()
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "")
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_new_visit_zelle_requires_bank_verification_and_keeps_its_actual_receipt_date(self):
        self.split_visit(member="check", amounts={"zelle": "5.00", "cash": "10.99"})
        day = timezone.localdate() - timedelta(days=1)
        self.input.update(zelle_sender="Fictional parent", received_on=day)
        with self.assertRaisesMessage(ValidationError, "business bank account"):
            self.confirm_split()
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        self.input["zelle_verified"] = True
        record = self.confirm_split()
        payment = record.checkout.sale.operations.get(tender="zelle")
        self.assertEqual(payment.manual_received_on, day)
        self.assertEqual(
            record.checkout.sale.operations.get(tender="cash").manual_received_on,
            timezone.localdate(),
        )
        self.assertEqual(
            record.purchase.installments.first().invoice.sale.operations.get().manual_received_on,
            timezone.localdate(),
        )
        self.assertEqual(record.checkout.details["zelle_sender"], "Fictional parent")
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("51.97"))

    def test_unselected_preview_cannot_confirm_a_placeholder_cash_membership(self):
        self.split_visit(member="")
        proposed = review(**self.options)
        values = self.input | {
            "member_accepted": True,
            "member_received": True,
            "member_card": self.options["method_id"],
        }
        self.assertEqual(proposed["facts"]["membership_due"], "35.98")
        self.assertFalse(ready(values, proposed))
        with self.assertRaisesMessage(ValidationError, "Choose how"):
            self.confirm_split()
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(MembershipPurchase.objects.exists())

    def test_unsupported_first_tenders_or_excess_visit_amounts_cannot_partially_save(self):
        self.split_visit()
        for tender in ("card", "wire", "split"):
            self.input["member_first_method"] = tender
            with self.subTest(tender=tender), self.assertRaises(ValidationError):
                self.confirm_split()
        self.input["member_first_method"] = "cash"
        self.input["split"] = {"cash": "20.00"}
        with self.assertRaises(ValidationError):
            self.confirm_split()
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_changed_tender_or_visit_split_requires_the_current_review(self):
        self.split_visit()
        accepted = review(**self.options)["fingerprint"]
        for change in ({"member_first_method": "check"}, {"split": {"cash": "11.00"}}):
            with self.subTest(change=change), self.assertRaisesMessage(ValidationError, "changed"):
                self.confirm_split(data=self.input | change, reviewed_hash=accepted)
        self.assertFalse(MembershipPurchase.objects.exists())

    def test_monthly_future_card_and_actual_membership_receipt_are_still_required(self):
        self.split_visit()
        for change in ({"method_id": None}, {"verified_received": False}, {"accepted": False}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.confirm_split(**change)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_prepaid_cash_uses_only_booking_card_for_the_visit_remainder(self):
        self.split_visit(billing="prepaid")
        record = self.confirm_split()
        self.assertIsNone(record.purchase.billing_state.mandate_id)
        self.assertEqual(
            received(record.purchase.installments.first().invoice.sale), Decimal("107.94")
        )
        self.assertEqual(record.checkout.sale.operations.get(tender="card").amount, Decimal("6.17"))
        self.assertEqual(record.facts["received_today"], "117.94")

    def test_existing_credit_can_fully_fund_membership_without_a_manual_receipt_acknowledgment(
        self,
    ):
        credit_arrivals.CreditFundedCardArrivalTests.card_visit(self, submit=False)
        self.options["data"].update(method="split", member_first_method="", split={"cash": "10.00"})
        proposed = review(**self.options)
        self.assertEqual(proposed["facts"]["membership_due"], "0.00")
        record = self.confirm_split(verified_received=False)
        self.assertFalse(record.purchase.installments.first().invoice.sale.operations.exists())
        self.assertEqual(record.checkout.sale.operations.get(tender="card").amount, Decimal("6.17"))
        self.assertEqual(receipt_summary(record)["new_received"], 10)

    def test_recorded_zelle_applies_only_to_visit_and_is_not_counted_as_new_money(self):
        from core.payments.zelle import record_receipt

        booking = self.split_visit(amounts={"cash": "5.99"})
        record_receipt(
            actor=self.staff,
            booking_id=booking.pk,
            request_key=uuid.uuid4(),
            value="10.00",
            sender_name="Fictional parent",
            verified=True,
        )
        record = self.confirm_split()
        self.assertEqual(record.facts["received_today"], "41.97")
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("41.97"))
        mail = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("Previously received Zelle applied to visit: $10.00", mail.text_body)
        self.assertIn("New payment received: $41.97", mail.text_body)

    def test_unknown_card_remainder_is_never_repeated_or_replaced_with_another_receipt(self):
        self.split_visit()
        record = self.confirm_split()
        operation = record.checkout.sale.operations.get(tender="card")
        record_result(operation_id=operation.pk, state="unknown", source="provider")
        before = PaymentOperation.objects.count(), FinancialPosting.objects.count()
        with patch("core.payments.operations.Gateway") as gateway:
            self.assertEqual(execute(operation.pk).state, "unknown")
            gateway.return_value.charge.assert_not_called()
        with self.assertRaisesMessage(ValidationError, "uncertain"):
            remainders.preview(
                actor=self.staff, booking_id=record.checkout.booking_id, method="cash"
            )
        self.assertEqual(
            before, (PaymentOperation.objects.count(), FinancialPosting.objects.count())
        )
        self.assertFalse(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").exists()
        )

    def test_known_visit_decline_can_be_resolved_with_cash_without_repeating_the_membership(self):
        self.split_visit()
        record = self.confirm_split()
        operation = record.checkout.sale.operations.get(tender="card")
        record_result(operation_id=operation.pk, state="declined", source="provider")
        args = dict(
            actor=self.staff,
            booking_id=record.checkout.booking_id,
            method="cash",
            context="follow_up",
        )
        proposal = remainders.preview(**args)
        remainders.confirm(
            **args, request_key=uuid.uuid4(), reviewed_hash=proposal[3], confirmed=True
        )
        self.assertEqual(MembershipPurchase.objects.count(), 1)
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("51.97"))
        self.assertIn(
            "New payment received: $51.97",
            MessageDelivery.objects.get(kind="membership_visit_confirmation").text_body,
        )

    def test_same_page_json_preserves_split_and_future_card_authority(self):
        booking = self.split_visit()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[booking.pk])
        page = self.client.get(url)
        values = self.web_data(booking) | {
            "arrival_draft": page.context["arrival_draft"],
            "cash_amount": "10.00",
        }
        quote = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(quote.status_code, 200, quote.content)
        data = quote.json()
        self.assertTrue(data["can_confirm"])
        self.assertEqual(data["membership_card_purchase"]["expected_method"], "cash")
        self.assertIn("record $45.98 and charge visit card $6.17", data["label"])
        self.assertIn("Cash to record", data["html"])
        result = self.client.post(
            url,
            values | {"confirm_review": "1", "reviewed_hash": data["hash"]},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(result.status_code, 200, result.content)
        self.assertTrue(result.json()["confirmed"])
        self.assertEqual(PaymentOperation.objects.count(), 3)
