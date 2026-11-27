"""Received membership splits stay distinct from visit and prior bank funds."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.communications.models import MessageDelivery
from core.customer_credit import applied, balance
from core.membership_arrival import confirm, receipt_summary, review
from core.membership_arrival_forms import ready
from core.membership_records import MembershipPurchase
from core.membership_sales import membership_status
from core.models import FinancialPosting, PaymentOperation
from core.payments.invoices import received
from core.payments.ledger import record_result
from tests import test_membership_arrival as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class ReceivedSplitMembershipArrivalTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.CombinedMembershipArrivalTests.prepare
    web_data = fixtures.CombinedMembershipArrivalTests.web_data

    def start(self, **changes):
        self.play = self.prepare(method="split", **changes)
        self.input.update(
            member_first_method="split",
            member_cash_amount="10.00",
            member_check_amount="5.00",
            member_zelle_amount="20.98",
            member_received_on=timezone.localdate() - timedelta(days=1),
            member_zelle_sender="Fictional separate membership transfer",
            member_zelle_verified=True,
            split={"cash": "10.00"},
        )
        return self.play

    def commit(self, **changes):
        values = self.options | dict(
            request_key=self.key,
            reviewed_hash=changes.get("reviewed_hash")
            or review(**(self.options | {k: v for k, v in changes.items() if k in self.options}))[
                "fingerprint"
            ],
            confirmed=True,
            accepted=True,
            verified_received=True,
        )
        return confirm(**(values | changes))

    def test_exact_membership_receipts_and_visit_card_conserve_dates_money_and_one_email(self):
        self.start()
        preview = review(**self.options)
        self.assertEqual(preview["facts"]["membership_due"], "35.98")
        self.assertEqual(preview["facts"]["received_today"], "45.98")
        self.assertEqual(preview["facts"]["payment_due_today"], "6.17")
        self.assertFalse(PaymentOperation.objects.exists())
        with self.runtime_role():
            record = self.commit()
            repeated = self.commit(reviewed_hash=preview["fingerprint"])
        self.assertEqual(record.pk, repeated.pk)
        member_sale = record.purchase.installments.first().invoice.sale
        self.assertEqual(received(member_sale), Decimal("35.98"))
        self.assertEqual(member_sale.operations.count(), 3)
        self.assertEqual(
            member_sale.operations.get(tender="zelle").manual_received_on,
            self.input["member_received_on"],
        )
        for tender in ("cash", "check"):
            self.assertEqual(
                member_sale.operations.get(tender=tender).manual_received_on, timezone.localdate()
            )
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("45.98"))
        self.assertEqual(membership_status(record.purchase), "active")
        self.assertEqual(self.play.membership_benefits.filter(current__status="used").count(), 2)
        self.assertEqual(PaymentOperation.objects.count(), 5)
        self.assertFalse(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").exists()
        )
        card = record.checkout.sale.operations.get(tender="card")
        self.assertEqual(card.amount, Decimal("6.17"))
        self.assertEqual(card.method_id, self.play.card_agreement.method_id)
        record_result(
            operation_id=card.pk, state="succeeded", source="provider", provider_reference="441091"
        )
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("52.15"))
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").count(), 1
        )
        message = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("New payment received: $52.15", message.text_body)
        self.assertFalse(MessageDelivery.objects.filter(kind="membership_confirmation").exists())
        self.assertEqual(record.purchase.installments.get(number=2).quote["total"], "37.06")

    def test_each_manual_proof_is_required_and_gift_cannot_substitute_for_cash(self):
        self.start()
        self.input.update(
            member_gift_card_amount="5.00", member_check_amount="0", member_zelle_verified=False
        )
        for data, verified, expected in (
            ({}, True, "physical gift card"),
            ({"gift_card_verified": True}, True, "bank account"),
            ({"gift_card_verified": True, "member_zelle_verified": True}, False, "cash/check"),
        ):
            with self.subTest(data=data), self.assertRaisesMessage(ValidationError, expected):
                self.commit(data=self.input | data, verified_received=verified)
            self.assertFalse(MembershipPurchase.objects.exists())
            self.assertFalse(PaymentOperation.objects.exists())
        self.input.update(gift_card_verified=True, member_zelle_verified=True)
        record = self.commit()
        self.assertEqual(
            record.purchase.installments.first()
            .invoice.sale.operations.get(tender="gift_card")
            .amount,
            Decimal("5"),
        )

    def test_partial_card_split_is_guarded_without_creating_or_collecting_anything(self):
        self.start()
        self.input["member_zelle_amount"] = "2"
        with self.assertRaisesMessage(ValidationError, "membership purchase page first"):
            review(**self.options)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())
        self.play.refresh_from_db()
        self.assertEqual(self.play.attendance, "")

    def test_changed_split_bank_date_or_sender_invalidates_accepted_review(self):
        self.start()
        accepted = review(**self.options)["fingerprint"]
        for changes in (
            {"member_cash_amount": "11", "member_check_amount": "4"},
            {"member_zelle_sender": "Another fictional sender"},
            {"member_received_on": timezone.localdate()},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaisesMessage(ValidationError, "changed"),
            ):
                self.commit(data=self.input | changes, reviewed_hash=accepted)
        self.assertFalse(MembershipPurchase.objects.exists())

    def test_prepaid_split_no_card_and_bank_only_split_no_cash_proof(self):
        self.start(billing="prepaid")
        self.input.update(
            member_cash_amount="0",
            member_check_amount="0",
            member_zelle_amount="107.94",
            split={"cash": "15.99"},
        )
        reviewed = review(**self.options)
        self.assertTrue(ready(self.input | {"member_add": True, "member_accepted": True}, reviewed))
        record = self.commit(verified_received=False)
        self.assertIsNone(record.purchase.billing_state.mandate_id)
        self.assertFalse(PaymentOperation.objects.filter(tender="card").exists())
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("123.93"))
        self.assertEqual(
            MessageDelivery.objects.filter(kind="membership_visit_confirmation").count(), 1
        )

    def test_monthly_still_needs_future_card_and_late_arrival_failure_rolls_back_all_receipts(self):
        self.start()
        with self.assertRaisesMessage(ValidationError, "current saved card"):
            self.commit(method_id=None)
        with patch(
            "core.membership_arrival.checkout.confirm",
            side_effect=ValidationError("Late arrival failure"),
        ):
            with self.assertRaisesMessage(ValidationError, "Late arrival failure"):
                self.commit()
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())

    def test_prior_booking_zelle_remains_visit_only_and_separate_from_membership_transfer(self):
        self.start()
        from core.payments.zelle import record_receipt

        record_receipt(
            actor=self.staff,
            booking_id=self.play.pk,
            request_key=uuid.uuid4(),
            value="10",
            sender_name="Prior visit transfer",
            verified=True,
        )
        self.input["split"] = {"cash": "5.99"}
        record = self.commit()
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("41.97"))
        self.assertEqual(record.checkout.sale.operations.get(tender="zelle").amount, Decimal("10"))
        self.assertEqual(
            record.purchase.installments.first().invoice.sale.operations.get(tender="zelle").amount,
            Decimal("20.98"),
        )
        message = MessageDelivery.objects.get(kind="membership_visit_confirmation")
        self.assertIn("Previously received Zelle applied to visit: $10.00", message.text_body)
        self.assertIn("New payment received: $41.97", message.text_body)

    def test_backed_credit_reduces_membership_split_and_is_not_new_money(self):
        self.conversion(card=True)
        self.start()
        self.selection["credit_amount"] = "10.00"
        self.input.update(member_zelle_amount="10.98", split={})
        before = PaymentOperation.objects.count()
        record = self.commit()
        sale = record.purchase.installments.first().invoice.sale
        self.assertEqual(applied(sale), Decimal("10"))
        self.assertEqual(received(sale), Decimal("25.98"))
        self.assertEqual(balance(self.customer.pk), Decimal("6.02"))
        self.assertEqual(receipt_summary(record)["new_received"], Decimal("25.98"))
        self.assertEqual(PaymentOperation.objects.count(), before + 3)

    def test_same_page_json_card_authority_and_draft_keep_membership_and_visit_amounts_separate(
        self,
    ):
        self.start()
        self.client.force_login(self.staff)
        url = reverse("booking_arrival", args=[self.play.pk])
        page = self.client.get(url)
        values = self.web_data(self.play) | {
            "arrival_draft": page.context["arrival_draft"],
            "cash_amount": "10.00",
        }
        response = self.client.post(url, values, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        self.assertTrue(result["can_confirm"])
        self.assertTrue(result["membership_needs_card"])
        self.assertEqual(result["membership_card_purchase"]["expected_method"], "split")
        self.assertEqual(result["membership_card_purchase"]["first_zelle"], "20.98")
        self.assertIn("record $45.98 and charge visit card $6.17", result["label"])
        restored = self.client.get(url, {"draft": values["arrival_draft"]})
        self.assertEqual(restored.context["form"]["member_check_amount"].value(), "5.00")
        final = self.client.post(
            url,
            values | {"confirm_review": "1", "reviewed_hash": result["hash"]},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(final.status_code, 200, final.content)
        self.assertTrue(final.json()["confirmed"])
        self.assertEqual(PaymentOperation.objects.count(), 5)
