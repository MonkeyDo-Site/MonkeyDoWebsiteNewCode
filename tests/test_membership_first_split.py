"""A first installment can contain actual received tenders and one card balance."""

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
from core.customer_credit_records import CustomerCreditApplication
from core.membership_payments import collect_installment, payment_review
from core.membership_records import MembershipPurchase
from core.membership_sales import card_required, membership_status, offer, purchase, today
from core.models import FinancialPosting, PaymentOperation
from core.payments.invoices import received, settled, total
from core.payments.ledger import record_result
from tests import test_membership_sales as fixtures
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class MembershipFirstSplitTests(RuntimeRoleMixin, TestCase):
    setUp = fixtures.MembershipPurchaseTests.setUp

    def selected(self, **changes):
        return (
            self.values
            | dict(expected_method="split", split={"cash": "10.00", "check": "5.00"})
            | changes
        )

    def buy_split(self, values=None, **changes):
        values = values or self.selected()
        return purchase(
            **values,
            request_key=self.key,
            reviewed=offer(**values)["fingerprint"],
            accepted=True,
            method_id=self.method.pk if card_required(offer(**values)) else None,
            verified_received=True,
            **changes,
        )

    def test_review_is_pure_and_only_the_remaining_first_principal_has_a_card_fee(self):
        data = offer(**self.selected())
        self.assertEqual(data["first_payment_total"], "36.61")
        self.assertEqual(data["first_payment_plan"]["card_total"], "21.61")
        self.assertEqual(data["installments"][0]["quote"]["processing_fee"], "0.63")
        self.assertEqual(data["installments"][1]["quote"]["total"], "37.06")
        self.assertIn("$10.00 cash", data["terms"])
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())

    def test_confirm_records_received_parts_once_and_waits_for_actual_card_result(self):
        values = self.selected()
        data = offer(**values)
        with self.runtime_role():
            member = self.buy_split()
            repeated = purchase(
                **values,
                request_key=self.key,
                reviewed=data["fingerprint"],
                accepted=True,
                method_id=self.method.pk,
                verified_received=True,
            )
        self.assertEqual(member.pk, repeated.pk)
        sale = member.installments.first().invoice.sale
        self.assertEqual(
            dict(sale.operations.values_list("tender", "amount")),
            {"cash": Decimal("10.00"), "check": Decimal("5.00"), "card": Decimal("21.61")},
        )
        self.assertEqual(received(sale), 15)
        self.assertEqual(membership_status(member), "pending")
        self.assertFalse(MessageDelivery.objects.exists())
        card = sale.operations.get(tender="card")
        record_result(
            operation_id=card.pk, state="succeeded", source="provider", provider_reference="441088"
        )
        self.assertEqual(received(sale), Decimal("36.61"))
        self.assertEqual(settled(sale), total(sale))
        self.assertEqual(membership_status(member), "active")
        self.assertEqual(MessageDelivery.objects.count(), 1)
        self.assertEqual(MembershipPurchase.objects.count(), 1)

    def test_prepaid_manual_split_needs_no_card_or_fabricated_card_operation(self):
        member = self.buy_split(
            self.selected(
                billing="prepaid", split={"cash": "50.00", "check": "30.00", "gift_card": "27.94"}
            ),
            gift_card_verified=True,
        )
        self.assertIsNone(member.billing_state.mandate_id)
        self.assertEqual(received(member.installments.first().invoice.sale), Decimal("107.94"))
        self.assertFalse(PaymentOperation.objects.filter(tender="card").exists())
        self.assertEqual(membership_status(member), "active")

    def test_monthly_manual_first_split_still_requires_future_card_consent(self):
        values = self.selected(split={"cash": "35.98"})
        with self.assertRaisesMessage(ValidationError, "saved card"):
            purchase(
                **values,
                request_key=self.key,
                reviewed=offer(**values)["fingerprint"],
                accepted=True,
                verified_received=True,
            )
        member = self.buy_split(values)
        self.assertEqual(member.billing_state.mandate.method_id, self.method.pk)
        self.assertFalse(PaymentOperation.objects.filter(tender="card").exists())
        self.assertEqual(member.installments.get(number=2).quote["total"], "37.06")

    def test_original_monthly_due_after_a_manual_first_split_uses_its_accepted_card(self):
        from core.membership_collections import schedule_installment

        member = self.buy_split(self.selected(split={"cash": "35.98"}))
        second = member.installments.get(number=2)
        with (
            override_settings(MEMBERSHIP_COLLECTIONS_ENABLED=True),
            patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=30)),
            patch("core.payments.operations.Gateway") as gateway,
        ):
            prepared = schedule_installment(second.pk)
            gateway.assert_not_called()
        self.assertEqual(prepared.operation.amount, Decimal("37.06"))
        self.assertEqual(prepared.operation.method_id, self.method.pk)
        self.assertIsNone(prepared.operation.actor_id)
        self.assertEqual(received(member.installments.first().invoice.sale), Decimal("35.98"))
        self.assertEqual(MessageDelivery.objects.count(), 1)

    def test_each_received_source_needs_its_own_strict_proof(self):
        values = self.selected(
            split={"cash": "10.00", "gift_card": "5.00", "zelle": "2.00"},
            split_sender="Fictional bank sender",
        )
        data = offer(**values)
        base = dict(
            request_key=self.key,
            reviewed=data["fingerprint"],
            accepted=True,
            method_id=self.method.pk,
        )
        for proofs in (
            dict(verified_received=1, gift_card_verified=True, zelle_verified=True),
            dict(verified_received=True, gift_card_verified=1, zelle_verified=True),
            dict(verified_received=True, gift_card_verified=True, zelle_verified=1),
        ):
            with self.subTest(proofs=proofs), self.assertRaises(ValidationError):
                purchase(**values, **base, **proofs)
        self.assertFalse(MembershipPurchase.objects.exists())
        member = purchase(
            **values, **base, verified_received=True, gift_card_verified=True, zelle_verified=True
        )
        self.assertEqual(received(member.installments.first().invoice.sale), 17)

    def test_zelle_bank_date_is_not_copied_to_todays_cash_or_check(self):
        day = today() - timedelta(days=1)
        member = self.buy_split(
            self.selected(
                split={"cash": "10.00", "check": "5.00", "zelle": "2.00"},
                split_sender=" Fictional sender ",
                split_received_on=day,
            ),
            zelle_verified=True,
        )
        sale = member.installments.first().invoice.sale
        self.assertEqual(sale.operations.get(tender="zelle").manual_received_on, day)
        self.assertEqual(sale.operations.get(tender="cash").manual_received_on, today())
        self.assertEqual(sale.operations.get(tender="check").manual_received_on, today())
        plan = member.installments.first().quote["initial_split"]
        self.assertEqual(
            next(row for row in plan["parts"] if row["tender"] == "zelle")["sender"],
            "Fictional sender",
        )

    def test_invalid_amounts_sources_and_future_bank_dates_create_nothing(self):
        for changes in (
            dict(split={"cash": "36.00"}),
            dict(split={"cash": 1.5}),
            dict(split={"cash": "-1"}),
            dict(split={"card": "10.00"}),
            dict(split={"zelle": "2.00"}),
            dict(
                split={"zelle": "2.00"},
                split_sender="Sender",
                split_received_on=today() + timedelta(days=1),
            ),
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                offer(**self.selected(**changes))
        self.assertFalse(MembershipPurchase.objects.exists())

    def test_split_amount_or_bank_identity_change_invalidates_the_review(self):
        values = self.selected()
        reviewed = offer(**values)
        with self.assertRaisesMessage(ValidationError, "changed"):
            purchase(
                **(values | dict(split={"cash": "11.00", "check": "5.00"})),
                request_key=self.key,
                reviewed=reviewed["fingerprint"],
                accepted=True,
                method_id=self.method.pk,
                verified_received=True,
            )
        self.assertFalse(MembershipPurchase.objects.exists())

    def test_late_queue_failure_rolls_back_all_receipts_and_the_purchase(self):
        with (
            patch("core.payments.jobs.enqueue", side_effect=ValidationError("late failure")),
            self.assertRaisesMessage(ValidationError, "late failure"),
        ):
            self.buy_split()
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())
        self.assertFalse(MessageDelivery.objects.exists())

    def test_known_card_decline_resolves_only_the_remaining_principal(self):
        member = self.buy_split()
        first = member.installments.first()
        record_result(
            operation_id=first.invoice.sale.operations.get(tender="card").pk,
            state="declined",
            source="provider",
            provider_reference="441089",
        )
        values = dict(actor=self.staff, member_id=member.pk, installment_id=first.pk, tender="cash")
        data = payment_review(**values)
        self.assertEqual(data["total"], "20.98")
        collect_installment(
            **values,
            request_key=uuid.uuid4(),
            reviewed=data["fingerprint"],
            confirmed=True,
            verified_received=True,
        )
        self.assertEqual(total(first.invoice.sale), Decimal("35.98"))
        self.assertEqual(received(first.invoice.sale), Decimal("35.98"))
        self.assertEqual(MessageDelivery.objects.filter(kind="membership_confirmation").count(), 1)

    def test_unknown_card_outcome_cannot_be_replaced_or_dispatched_twice(self):
        member = self.buy_split()
        first = member.installments.first()
        record_result(
            operation_id=first.invoice.sale.operations.get(tender="card").pk,
            state="unknown",
            source="provider",
        )
        with self.assertRaises(ValidationError):
            payment_review(
                actor=self.staff, member_id=member.pk, installment_id=first.pk, tender="cash"
            )
        self.assertEqual(received(first.invoice.sale), 15)

    def test_same_page_live_review_and_native_confirmation_keep_the_actual_tenders(self):
        self.client.force_login(self.staff)
        values = {
            "customer": self.customer.pk,
            "kind": "subscription",
            "places": 2,
            "months": 3,
            "billing": "monthly",
            "starts_on": self.values["starts_on"].isoformat(),
            "expected_method": "split",
            "first_cash": "10.00",
            "first_check": "5.00",
            "request_key": str(self.key),
        }
        preview = self.client.post(reverse("membership_offer"), values)
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(preview.json()["split_card_total"], "21.61")
        self.assertEqual(preview.json()["split_manual_total"], "15.00")
        self.assertTrue(preview.json()["needs_card"])
        self.assertFalse(MembershipPurchase.objects.exists())
        final = self.client.post(
            reverse("membership_purchase"),
            values
            | {
                "action": "confirm",
                "reviewed": preview.json()["fingerprint"],
                "accepted": "on",
                "verified_received": "on",
                "method": str(self.method.pk),
            },
        )
        self.assertEqual(final.status_code, 302, final.content)
        member = MembershipPurchase.objects.get()
        detail = self.client.get(reverse("membership_overview", args=[member.pk]))
        self.assertContains(detail, "$15.00")
        self.assertContains(detail, "$21.61")
        self.assertEqual(member.installments.first().invoice.sale.operations.count(), 3)

    def test_prepaid_live_quote_only_requires_a_card_for_its_remaining_card_part(self):
        self.client.force_login(self.staff)
        values = {
            "customer": self.customer.pk,
            "kind": "subscription",
            "places": 2,
            "months": 3,
            "billing": "prepaid",
            "starts_on": self.values["starts_on"].isoformat(),
            "expected_method": "split",
            "first_cash": "100.00",
        }
        preview = self.client.post(reverse("membership_offer"), values)
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertTrue(preview.json()["needs_card"])
        self.assertEqual(preview.json()["split_card_total"], "8.18")
        all_cash = self.client.post(reverse("membership_offer"), values | {"first_cash": "107.94"})
        self.assertEqual(all_cash.status_code, 200, all_cash.content)
        self.assertFalse(all_cash.json()["needs_card"])
        self.assertEqual(all_cash.json()["split_card_total"], "0.00")


@override_settings(**SETTINGS)
class MembershipFirstSplitCreditTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    def test_existing_credit_does_not_increase_the_card_fee_over_manual_funds(self):
        _, original, prior, _ = self.conversion(card=True)
        values = self.values(credit="10.00", expected_method="split", split={"cash": "3.00"})
        data = offer(**values)
        self.assertEqual(data["first_payment_total"], "8.14")
        self.assertEqual(data["first_payment_plan"]["card_total"], "5.14")
        with self.runtime_role():
            member = self.buy(values, method=prior.billing_state.mandate.method, verified=True)
        sale = member.installments.first().invoice.sale
        self.assertEqual((applied(sale), received(sale), total(sale)), (10, 3, Decimal("18.14")))
        self.assertEqual(balance(self.customer.pk), Decimal("6.02"))
        self.assertEqual(received(original), Decimal("16.47"))
        self.assertEqual(total(original), Decimal("0.45"))
        self.assertEqual(CustomerCreditApplication.objects.count(), 1)

    def test_full_credit_with_zero_received_parts_has_no_zero_receipt(self):
        _, _, prior, _ = self.conversion(card=True, children=2, adults=2)
        before = PaymentOperation.objects.count()
        available = balance(self.customer.pk)
        values = self.values(credit="17.99", expected_method="split", split={})
        member = self.buy(values, method=prior.billing_state.mandate.method)
        sale = member.installments.first().invoice.sale
        self.assertFalse(sale.operations.exists())
        self.assertEqual(PaymentOperation.objects.count(), before)
        self.assertEqual(applied(sale), Decimal("17.99"))
        self.assertEqual(balance(self.customer.pk), available - Decimal("17.99"))
        self.assertEqual(membership_status(member), "active")

    def test_source_hold_or_late_failure_does_not_spend_credit_or_record_manual_money(self):
        _, original, prior, _ = self.conversion(card=True)
        values = self.values(credit="10.00", expected_method="split", split={"cash": "3.00"})
        before = PaymentOperation.objects.count()
        with (
            patch("core.payments.jobs.enqueue", side_effect=ValidationError("late failure")),
            self.assertRaises(ValidationError),
        ):
            self.buy(values, method=prior.billing_state.mandate.method, verified=True)
        self.assertFalse(CustomerCreditApplication.objects.exists())
        self.assertEqual(balance(self.customer.pk), Decimal("16.02"))
        self.assertEqual(PaymentOperation.objects.count(), before)
        self.external_return(original.operations.get(kind="receipt"))
        with self.assertRaises(ValidationError):
            offer(**values)
