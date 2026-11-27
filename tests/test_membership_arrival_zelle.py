"""New membership Zelle is distinct from already recorded visit bank funds."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.communications.models import MessageDelivery
from core.membership_arrival import receipt_summary, review
from core.membership_records import MembershipPurchase
from core.models import FinancialPosting, PaymentOperation
from core.payments.ledger import record_result
from core.payments.models import ZelleReceipt
from core.payments.zelle import record_receipt, unallocated
from tests import test_membership_arrival as arrivals
from tests import test_membership_arrival_card as credit_arrivals
from tests import test_membership_arrival_split as split_arrivals
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class SeparateMembershipZelleTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = arrivals.CombinedMembershipArrivalTests.prepare
    web_data = arrivals.CombinedMembershipArrivalTests.web_data
    split_visit = split_arrivals.SplitMembershipArrivalTests.split_visit
    confirm_split = split_arrivals.SplitMembershipArrivalTests.confirm_split

    def bank_transfer(self, **changes):
        booking = self.split_visit(member="zelle", **changes)
        self.bank_day = timezone.localdate() - timedelta(days=1)
        self.input.update(
            member_received_on=self.bank_day,
            member_zelle_sender="Fictional membership sender",
            member_zelle_verified=True,
        )
        return booking

    def test_new_bank_money_keeps_separate_receipt_date_source_and_actual_amounts_once(self):
        booking = self.bank_transfer()
        before = review(**self.options)
        self.assertEqual(before["facts"]["membership_zelle"]["amount"], "35.98")
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        with self.runtime_role():
            record = self.confirm_split(verified_received=False)
            self.assertEqual(
                self.confirm_split(reviewed_hash=record.fingerprint, verified_received=False).pk,
                record.pk,
            )
        member_payment = record.purchase.installments.first().invoice.sale.operations.get()
        self.assertEqual(member_payment.tender, "zelle")
        self.assertEqual(member_payment.amount, Decimal("35.98"))
        self.assertEqual(member_payment.manual_received_on, self.bank_day)
        self.assertEqual(
            record.checkout.sale.operations.get(tender="cash").manual_received_on,
            timezone.localdate(),
        )
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("45.98"))
        self.assertFalse(ZelleReceipt.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 3)
        self.assertEqual(record.purchase.installments.get(number=2).quote["total"], "37.06")
        self.assertFalse(MessageDelivery.objects.filter(kind="membership_visit_confirmation"))
        record_result(
            operation_id=record.checkout.sale.operations.get(tender="card").pk,
            state="succeeded",
            source="provider",
            provider_reference="441081",
        )
        mail = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("New payment received: $52.15", mail.text_body)
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("52.15"))
        self.client.force_login(self.staff)
        detail = self.client.get(reverse("booking_detail", args=[booking.pk]))
        self.assertContains(detail, "Separate membership Zelle: $35.98")
        self.assertContains(detail, "Fictional membership sender")

    def test_membership_bank_proof_cannot_be_replaced_by_the_cash_acknowledgment(self):
        self.bank_transfer()
        for flag in (False, None, "yes", 1):
            self.input["member_zelle_verified"] = flag
            with (
                self.subTest(flag=flag),
                self.assertRaisesMessage(ValidationError, "separate membership Zelle transfer"),
            ):
                self.confirm_split(verified_received=True)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_membership_and_visit_bank_proofs_and_bank_dates_remain_distinct(self):
        self.bank_transfer(amounts={"zelle": "5.00", "cash": "10.99"})
        visit_day = self.bank_day - timedelta(days=1)
        self.input.update(received_on=visit_day, zelle_sender="Fictional visit sender")
        with self.assertRaisesMessage(ValidationError, "business bank account"):
            self.confirm_split()
        self.input.update(zelle_verified=True, member_zelle_verified=False)
        with self.assertRaisesMessage(ValidationError, "separate membership"):
            self.confirm_split()
        self.input["member_zelle_verified"] = True
        record = self.confirm_split(verified_received=False)
        self.assertEqual(
            record.checkout.sale.operations.get(tender="zelle").manual_received_on, visit_day
        )
        self.assertEqual(
            record.purchase.installments.first().invoice.sale.operations.get().manual_received_on,
            self.bank_day,
        )
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("51.97"))

    def test_previously_recorded_visit_receipt_is_not_reused_as_new_membership_money(self):
        booking = self.bank_transfer(amounts={"cash": "5.99"})
        receipt = record_receipt(
            actor=self.staff,
            booking_id=booking.pk,
            request_key=uuid.uuid4(),
            value="10.00",
            sender_name="Earlier visit sender",
            verified=True,
        )
        record = self.confirm_split(verified_received=False)
        self.assertEqual(unallocated(receipt), 0)
        self.assertEqual(ZelleReceipt.objects.get().amount, Decimal("10.00"))
        self.assertEqual(
            record.purchase.installments.first().invoice.sale.operations.get().amount,
            Decimal("35.98"),
        )
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("41.97"))
        mail = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("Previously received Zelle applied to visit: $10.00", mail.text_body)
        self.assertIn("New payment received: $41.97", mail.text_body)

    def test_receipt_date_and_sender_validation_creates_no_financial_facts(self):
        self.bank_transfer()
        cases = (
            {"member_received_on": timezone.localdate() + timedelta(days=1)},
            {"member_received_on": datetime.now()},
            {"member_received_on": "2026-01-01"},
            {"member_zelle_sender": ""},
            {"member_zelle_sender": "x" * 161},
        )
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                review(**(self.options | {"data": self.input | change}))
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_changed_sender_or_date_invalidates_the_accepted_review(self):
        self.bank_transfer()
        old = review(**self.options)["fingerprint"]
        for change in (
            {"member_zelle_sender": "Different bank sender"},
            {"member_received_on": timezone.localdate()},
        ):
            with self.subTest(change=change), self.assertRaisesMessage(ValidationError, "changed"):
                self.confirm_split(data=self.input | change, reviewed_hash=old)
        self.assertFalse(PaymentOperation.objects.exists())

    def test_prepaid_bank_transfer_needs_no_membership_card(self):
        self.bank_transfer(billing="prepaid")
        record = self.confirm_split(verified_received=False)
        self.assertIsNone(record.purchase.billing_state.mandate_id)
        first = record.purchase.installments.first().invoice.sale.operations.get()
        self.assertEqual(
            (first.amount, first.manual_received_on), (Decimal("107.94"), self.bank_day)
        )
        self.assertEqual(record.checkout.sale.operations.get(tender="card").amount, Decimal("6.17"))

    def test_zero_visit_creates_only_the_membership_bank_receipt(self):
        booking = self.bank_transfer(children=2, amounts={"cash": "0.00"})
        record = self.confirm_split(verified_received=False)
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.get().tender, "zelle")
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("35.98"))
        self.assertEqual(booking.membership_benefits.filter(current__status="used").count(), 2)

    def test_credit_funding_needs_no_fabricated_bank_transfer_or_bank_proof(self):
        credit_arrivals.CreditFundedCardArrivalTests.card_visit(self, submit=False)
        self.input = self.options["data"]
        self.input.update(method="split", member_first_method="zelle", split={"cash": "10.00"})
        record = self.confirm_split(verified_received=False)
        self.assertNotIn("membership_zelle", record.facts)
        self.assertFalse(record.purchase.installments.first().invoice.sale.operations.exists())

    def test_late_failure_rolls_back_new_bank_money_and_leaves_prior_visit_funds_available(self):
        booking = self.bank_transfer(amounts={"cash": "5.99"})
        receipt = record_receipt(
            actor=self.staff,
            booking_id=booking.pk,
            request_key=uuid.uuid4(),
            value="10.00",
            sender_name="Earlier visit",
            verified=True,
        )
        with (
            patch(
                "core.membership_arrival.queue_confirmation",
                side_effect=ValidationError("late failure"),
            ),
            self.assertRaisesMessage(ValidationError, "late failure"),
        ):
            self.confirm_split(verified_received=False)
        booking.refresh_from_db()
        self.assertEqual(booking.attendance, "")
        self.assertEqual(unallocated(receipt), Decimal("10.00"))
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())

    def test_same_page_review_demands_bank_proof_and_confirms_exact_receipt_date(self):
        booking = self.bank_transfer()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[booking.pk])
        initial = self.client.get(url)
        values = self.web_data(booking) | {
            "arrival_draft": initial.context["arrival_draft"],
            "cash_amount": "10.00",
            "member_received_on": self.bank_day.isoformat(),
            "member_zelle_verified": "",
        }
        quote = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(quote.status_code, 200, quote.content)
        self.assertFalse(quote.json()["can_confirm"])
        values["member_zelle_verified"] = "on"
        quote = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(quote.status_code, 200, quote.content)
        self.assertTrue(quote.json()["can_confirm"])
        self.assertEqual(quote.json()["membership_card_purchase"]["expected_method"], "zelle")
        result = self.client.post(
            url,
            values | {"confirm_review": "1", "reviewed_hash": quote.json()["hash"]},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(result.status_code, 200, result.content)
        self.assertTrue(result.json()["confirmed"])
        self.assertEqual(
            PaymentOperation.objects.get(tender="zelle").manual_received_on, self.bank_day
        )

    def test_card_navigation_preserves_separate_bank_details_without_recording_money(self):
        booking = self.bank_transfer()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[booking.pk])
        initial = self.client.get(url)
        token = initial.context["arrival_draft"]
        values = self.web_data(booking) | {
            "arrival_draft": token,
            "cash_amount": "10.00",
            "member_received_on": self.bank_day.isoformat(),
            "member_zelle_verified": "on",
            "continue_to": "card",
        }
        leaving = self.client.post(url, values)
        self.assertRedirects(
            leaving,
            reverse("booking_card_change", args=[booking.pk]) + "?draft=" + token,
            fetch_redirect_response=False,
        )
        resumed = self.client.get(url, {"draft": token})
        form = resumed.context["form"]
        self.assertEqual(form["member_first_method"].value(), "zelle")
        self.assertEqual(form["member_received_on"].value(), self.bank_day.isoformat())
        self.assertEqual(form["member_zelle_sender"].value(), "Fictional membership sender")
        self.assertTrue(form["member_zelle_verified"].value())
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
