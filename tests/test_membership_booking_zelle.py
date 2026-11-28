"""One recorded transfer can fund membership and visit, without new money twice."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.communications.models import MessageDelivery
from core.membership_arrival import receipt_summary, review
from core.membership_bank import applied
from core.membership_records import MembershipBankAllocation, MembershipPurchase
from core.models import FinancialPosting, PaymentOperation
from core.payments.invoices import received
from core.payments.models import ZelleApplication, ZelleReceipt, ZelleRefund
from core.payments.zelle import facts, record_receipt
from tests import test_membership_arrival as fixtures
from tests import test_membership_arrival_first_split as split_fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class MembershipBookingZelleTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.CombinedMembershipArrivalTests.prepare
    web_data = fixtures.CombinedMembershipArrivalTests.web_data
    commit = split_fixtures.ReceivedSplitMembershipArrivalTests.commit

    def start(self, *, bank="25", assigned="20", **changes):
        self.play = self.prepare(method="split", **changes)
        self.bank = record_receipt(
            actor=self.staff,
            booking_id=self.play.pk,
            request_key=uuid.uuid4(),
            value=bank,
            received_on=timezone.localdate() - timedelta(days=2),
            sender_name="Fictional original bank transfer",
            verified=True,
        )
        self.input.update(
            member_first_method="split",
            member_recorded_zelle=assigned,
            member_cash_amount="10",
            member_check_amount="5.98",
            split={"cash": "10.99"},
        )
        return self.play

    def test_one_original_transfer_funds_both_invoices_without_being_new_money_twice(self):
        self.start()
        proposed = review(**self.options)
        self.assertEqual(proposed["facts"]["membership_due"], "15.98")
        self.assertEqual(proposed["facts"]["membership_prepaid"], "20.00")
        self.assertEqual(proposed["facts"]["received_today"], "26.97")
        self.assertEqual(facts(self.play)["available"], Decimal("25"))
        self.assertFalse(MembershipBankAllocation.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        with self.runtime_role():
            record = self.commit(reviewed_hash=proposed["fingerprint"])
            again = self.commit(reviewed_hash=proposed["fingerprint"])
        self.assertEqual(record.pk, again.pk)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
        member_sale = record.purchase.installments.first().invoice.sale
        self.assertEqual(received(member_sale), Decimal("35.98"))
        self.assertEqual(received(record.checkout.sale), Decimal("15.99"))
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("26.97"))
        self.assertEqual(applied(record.purchase), Decimal("20"))
        self.assertEqual(ZelleReceipt.objects.count(), 1)
        self.assertEqual(ZelleApplication.objects.count(), 2)
        self.assertEqual(MembershipBankAllocation.objects.count(), 1)
        self.assertEqual(PaymentOperation.objects.count(), 5)
        self.assertEqual(facts(self.play)["available"], 0)
        self.assertEqual(facts(self.play)["refund_due"], 0)
        bank_part = MembershipBankAllocation.objects.get()
        self.assertEqual(bank_part.receipt_id, self.bank.pk)
        self.assertEqual(bank_part.operation.manual_received_on, self.bank.received_on)
        self.assertEqual(bank_part.operation.amount, Decimal("20"))
        self.assertEqual(record.purchase.installments.get(number=2).quote["total"], "37.06")
        message = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("Previously received Zelle applied to membership: $20.00", message.text_body)
        self.assertIn("Previously received Zelle applied to visit: $5.00", message.text_body)
        self.assertIn("New payment received: $26.97", message.text_body)
        self.assertIn("Membership payment received: $15.98", message.text_body)
        self.assertFalse(PaymentOperation.objects.filter(tender="card").exists())

    def test_full_first_payment_from_old_bank_needs_no_new_receipt_proof_but_keeps_future_card(
        self,
    ):
        self.start(bank="60", assigned="35.98")
        self.input.update(member_cash_amount="0", member_check_amount="0", split={})
        record = self.commit(verified_received=False)
        self.assertEqual(record.purchase.installments.first().invoice.sale.operations.count(), 1)
        self.assertEqual(applied(record.purchase), Decimal("35.98"))
        self.assertEqual(receipt_summary(record)["new_received"], 0)
        self.play.refresh_from_db()
        self.assertEqual(facts(self.play)["refund_due"], Decimal("8.03"))
        self.assertIsNotNone(record.purchase.billing_state.mandate_id)
        self.assertEqual(ZelleReceipt.objects.count(), 1)
        from core.payments.zelle import complete_refund

        with self.runtime_role():
            complete_refund(
                actor=self.owner,
                booking_id=self.play.pk,
                request_key=uuid.uuid4(),
                reviewed_amount="8.03",
                confirmed=True,
            )
        self.assertEqual(facts(self.play)["available"], 0)
        self.assertEqual(facts(self.play)["refund_due"], 0)
        self.assertEqual(applied(record.purchase), Decimal("35.98"))

    def test_missing_changed_or_excess_sources_cannot_record_a_partial_purchase(self):
        self.start()
        old = review(**self.options)["fingerprint"]
        for change in (
            {"member_recorded_zelle": "26"},
            {"member_recorded_zelle": "36"},
            {"member_recorded_zelle": "19", "member_check_amount": "6.98"},
        ):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.commit(data=self.input | change, reviewed_hash=old)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertEqual(facts(self.play)["available"], Decimal("25"))

    def test_new_bank_receipt_after_preview_makes_review_stale_without_spending_it(self):
        self.start()
        old = review(**self.options)["fingerprint"]
        record_receipt(
            actor=self.staff,
            booking_id=self.play.pk,
            request_key=uuid.uuid4(),
            value="1",
            sender_name="Another fictional transfer",
            verified=True,
        )
        self.input["split"] = {"cash": "9.99"}
        with self.assertRaisesMessage(ValidationError, "changed"):
            self.commit(reviewed_hash=old)
        self.assertFalse(MembershipBankAllocation.objects.exists())
        self.assertEqual(facts(self.play)["available"], Decimal("26"))

    def test_late_arrival_failure_rolls_back_bank_application_and_new_receipts_together(self):
        self.start()
        with patch(
            "core.membership_arrival.checkout.confirm",
            side_effect=ValidationError("late test failure"),
        ):
            with self.assertRaisesMessage(ValidationError, "late test failure"):
                self.commit()
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertFalse(ZelleApplication.objects.exists())
        self.assertEqual(facts(self.play)["available"], Decimal("25"))

    def test_receipt_budget_and_membership_evidence_are_enforced_by_postgresql(self):
        self.start()
        record = self.commit()
        bank = MembershipBankAllocation.objects.get()

        def rewrite():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE core_membershipbankallocation SET amount=19 WHERE operation_id=%s",
                    [bank.pk],
                )

        for action in (
            rewrite,
            lambda: ZelleRefund.objects.create(
                receipt=self.bank,
                request_key=uuid.uuid4(),
                amount="0.01",
                completed_on=timezone.localdate(),
                actor=self.staff,
            ),
        ):
            with self.assertRaises(DatabaseError), transaction.atomic(), self.runtime_role():
                action()
        self.assertEqual(applied(record.purchase), Decimal("20"))
        self.assertEqual(facts(self.play)["available"], 0)

    def test_live_json_shortcuts_and_status_use_only_bank_remaining_after_membership(self):
        self.start()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url)
        values = self.web_data(self.play) | {
            "arrival_draft": page.context["arrival_draft"],
            "cash_amount": "10.99",
        }
        quote = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(quote.status_code, 200, quote.content)
        data = quote.json()
        self.assertTrue(data["can_confirm"])
        self.assertEqual(data["prepaid_available"], "5.00")
        self.assertEqual(data["membership_card_purchase"]["first_bank_amount"], "20")
        self.assertEqual(data["membership_card_purchase"]["first_bank_booking"], self.play.pk)
        self.assertIn("$26.97", data["label"])
        result = self.client.post(
            url,
            values | {"confirm_review": "1", "reviewed_hash": data["hash"]},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(result.status_code, 200, result.content)
        self.assertTrue(result.json()["confirmed"])
        status = self.client.get(result.json()["status_url"])
        self.assertEqual(status.json()["received"], "26.97")
        detail = self.client.get(reverse("booking_detail", args=[self.play.pk]))
        self.assertContains(detail, "New payment received: $26.97")
        self.assertContains(detail, "Previously received Zelle applied to membership: $20.00")

    def test_multiple_original_transfers_are_consumed_in_original_bank_date_order(self):
        self.start(bank="10", assigned="20")
        second = record_receipt(
            actor=self.staff,
            booking_id=self.play.pk,
            request_key=uuid.uuid4(),
            value="20",
            received_on=timezone.localdate() - timedelta(days=1),
            sender_name="Second fictional transfer",
            verified=True,
        )
        self.input["split"] = {"cash": "5.99"}
        record = self.commit()
        allocations = list(
            record.purchase.bank_allocations.select_related("receipt", "operation").order_by(
                "receipt__received_on"
            )
        )
        self.assertEqual(
            [(x.receipt_id, x.amount) for x in allocations],
            [(self.bank.pk, Decimal("10")), (second.pk, Decimal("10"))],
        )
        for item in allocations:
            self.assertEqual(item.operation.manual_received_on, item.receipt.received_on)
        self.assertEqual(ZelleReceipt.objects.count(), 2)
        self.assertEqual(facts(self.play)["available"], 0)
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("21.97"))

    def test_other_customer_and_standalone_purchase_cannot_take_this_booking_transfer(self):
        from core.membership_bank import review as bank_review
        from core.membership_sales import offer, purchase
        from core.models import Customer

        self.start()
        other = Customer.objects.create(
            last_name="Other", phone="2025550999", email="other@example.invalid"
        )
        with self.assertRaisesMessage(ValidationError, "customer's upcoming booking"):
            bank_review(actor=self.staff, customer=other, booking_id=self.play.pk, value="10")
        values = dict(
            actor=self.staff,
            customer=self.customer,
            **self.selection,
            expected_method="split",
            split={"cash": "15.98"},
            bank_booking_id=self.play.pk,
            bank_amount="20",
        )
        accepted = offer(**values)
        with self.assertRaisesMessage(ValidationError, "combined membership and arrival"):
            purchase(
                **values,
                request_key=uuid.uuid4(),
                reviewed=accepted["fingerprint"],
                accepted=True,
                method_id=self.options["method_id"],
                verified_received=True,
            )
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(MembershipBankAllocation.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_existing_credit_and_recorded_bank_share_only_the_remaining_membership_principal(self):
        from core.customer_credit import applied as credit_applied
        from core.customer_credit import balance

        self.conversion(card=True)
        self.start()
        self.selection["credit_amount"] = "10"
        self.input.update(member_cash_amount="5.98", member_check_amount="0", split={})
        record = self.commit()
        sale = record.purchase.installments.first().invoice.sale
        self.assertEqual(credit_applied(sale), Decimal("10"))
        self.assertEqual(applied(record.purchase), Decimal("20"))
        self.assertEqual(received(sale), Decimal("25.98"))
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("5.98"))
        self.assertEqual(balance(self.customer.pk), Decimal("6.02"))
        self.assertEqual(facts(self.play)["available"], Decimal("5"))
        from core.payments.checkout import summary

        self.play.refresh_from_db()
        self.assertEqual(summary(self.play)["total_received"], Decimal("5"))
        self.assertEqual(summary(self.play)["status"], "Zelle refund due")
        self.assertEqual(record.purchase.installments.get(number=2).quote["total"], "37.06")
