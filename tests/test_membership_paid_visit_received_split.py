"""Actual new split receipts fund only the paid visit's remaining membership amount."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from core.communications.models import MessageDelivery
from core.customer_credit import applied, balance
from core.customer_credit_records import VisitMembershipConversion
from core.membership_records import MembershipPurchase
from core.membership_sales import installment_paid, offer, purchase, today
from core.models import MembershipDraft, PaymentOperation
from core.payments.invoices import received, total
from tests import test_membership_paid_visit as fixtures
from tests.helpers import verified_owner_login
from tests.test_membership_initial_credit import SETTINGS, InitialCreditFixtures
from tests.test_payment_runtime_grants import RuntimeRoleMixin


@override_settings(**SETTINGS)
class PaidVisitReceivedSplitTests(InitialCreditFixtures, RuntimeRoleMixin, TestCase):
    prepare = fixtures.PaidVisitPurchaseTests.prepare
    web_values = fixtures.PaidVisitPurchaseTests.web_values

    def options_for_split(self, **changes):
        self.prepare(card=True, expected_method="split", **changes)
        self.options.update(
            split={"cash": ".50", "check": ".50", "zelle": ".47", "gift_card": ".50"},
            split_sender=" Fictional bank sender ",
            split_received_on=today() - timedelta(days=1),
        )
        return self.options

    def buy_split(self, options=None, *, key=None, **proofs):
        values = options or self.options
        data = offer(**values)
        return purchase(
            **values,
            request_key=key or uuid.uuid4(),
            reviewed=data["fingerprint"],
            accepted=True,
            method_id=self.method.pk if values["billing"] == "monthly" else None,
            **(dict(verified_received=True, gift_card_verified=True, zelle_verified=True) | proofs),
        )

    def assert_complete(self, member):
        first = member.installments.first()
        self.assertTrue(installment_paid(first))
        self.assertEqual(applied(first.invoice.sale), Decimal("16.02"))
        self.assertEqual(received(first.invoice.sale), Decimal("1.97"))
        self.assertEqual(total(first.invoice.sale), Decimal("17.99"))
        self.assertEqual(received(self.original), Decimal("16.47"))
        self.assertEqual(total(self.original), Decimal(".45"))
        self.assertEqual(balance(self.customer.pk), 0)
        self.assertEqual(self.visit.membership_benefits.filter(current__status="used").count(), 1)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS core_paid_visit_purchase_complete IMMEDIATE")
            cursor.execute("SET CONSTRAINTS core_paid_visit_purchase_complete DEFERRED")

    def test_four_distinct_receipts_keep_actual_dates_and_only_new_remaining_money(self):
        self.options_for_split()
        data = offer(**self.options)
        self.assertEqual(data["first_payment_total"], "1.97")
        self.assertEqual(data["first_payment_plan"]["card_total"], "0.00")
        self.assertEqual(data["first_payment_plan"]["credit_amount"], "16.02")
        self.assertIn("$0.47 verified Zelle", data["terms"])
        self.assertNotIn("$16.50 card", data["terms"])
        self.assertFalse(VisitMembershipConversion.objects.exists())
        with self.runtime_role():
            member = self.buy_split()
        self.assert_complete(member)
        operations = member.installments.first().invoice.sale.operations
        self.assertEqual(
            dict(operations.values_list("tender", "amount")),
            {
                "cash": Decimal(".50"),
                "check": Decimal(".50"),
                "zelle": Decimal(".47"),
                "gift_card": Decimal(".50"),
            },
        )
        for op in operations.all():
            self.assertEqual(
                op.manual_received_on,
                today() - timedelta(days=1) if op.tender == "zelle" else today(),
            )
        self.assertEqual(
            next(p for p in data["first_payment_plan"]["parts"] if p["tender"] == "zelle")[
                "sender"
            ],
            "Fictional bank sender",
        )
        self.assertEqual(member.installments.get(number=2).quote["total"], "18.53")
        self.assertEqual(PaymentOperation.objects.count(), 5)
        self.assertEqual(MessageDelivery.objects.filter(membership=member).count(), 1)
        self.assertIn(
            "New membership payment received: $1.97",
            MessageDelivery.objects.get(membership=member).text_body,
        )

    def test_zelle_only_and_gift_only_remainders_use_independent_required_verification(self):
        self.options_for_split()
        for tender, proof in (("zelle", "zelle_verified"), ("gift_card", "gift_card_verified")):
            with self.subTest(tender=tender):
                values = self.options | dict(split={tender: "1.97"})
                with self.assertRaises(ValidationError):
                    self.buy_split(values, **{proof: False})
                self.assertFalse(MembershipPurchase.objects.exists())
        member = self.buy_split(
            self.options | dict(split={"zelle": "1.97"}),
            verified_received=False,
            gift_card_verified=False,
        )
        self.assert_complete(member)
        self.assertEqual(member.installments.first().invoice.sale.operations.get().tender, "zelle")

    def test_gift_only_succeeds_without_cash_or_zelle_proof_and_no_external_debit(self):
        self.options_for_split()
        with patch("core.payments.operations.Gateway") as gateway:
            member = self.buy_split(
                self.options | dict(split={"gift_card": "1.97"}),
                verified_received=False,
                zelle_verified=False,
            )
        gateway.assert_not_called()
        self.assert_complete(member)
        self.assertEqual(
            member.installments.first().invoice.sale.operations.get().tender, "gift_card"
        )

    def test_all_three_proofs_are_strict_booleans_before_purchase_or_conversion(self):
        self.options_for_split()
        for field in ("verified_received", "gift_card_verified", "zelle_verified"):
            for value in (False, 1, "yes"):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    self.buy_split(**{field: value})
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_preview_can_show_uncovered_amount_but_confirm_cannot_consume_original_funds(self):
        self.options_for_split()
        values = self.options | dict(split={"cash": "1.00"})
        data = offer(**values)
        self.assertEqual(data["first_payment_plan"]["card_total"], "0.00")
        self.assertEqual(data["first_payment_plan"]["unallocated"], "0.97")
        self.assertEqual(data["first_payment_total"], "1.97")
        with self.assertRaisesMessage(ValidationError, "remaining membership amount"):
            self.buy_split(values)
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertEqual(received(self.original), Decimal("16.47"))
        self.assertEqual(total(self.original), Decimal("16.47"))
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_excess_amount_missing_sender_or_future_bank_date_is_rejected(self):
        self.options_for_split()
        for changes in (
            dict(split={"cash": "1.98"}),
            dict(split_sender=""),
            dict(split_received_on=today() + timedelta(days=1)),
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                offer(**(self.options | changes))
        self.assertFalse(MembershipPurchase.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_replay_returns_same_purchase_and_all_source_receipts_once(self):
        self.options_for_split()
        values = self.options.copy()
        data = offer(**values)
        key = uuid.uuid4()
        member = self.buy_split(values, key=key)
        again = purchase(
            **values,
            request_key=key,
            reviewed=data["fingerprint"],
            accepted=True,
            verified_received=True,
            gift_card_verified=True,
            zelle_verified=True,
            method_id=self.method.pk,
        )
        self.assertEqual(member.pk, again.pk)
        self.assertEqual(PaymentOperation.objects.count(), 5)
        self.assertEqual(VisitMembershipConversion.objects.count(), 1)

    def test_late_failure_rolls_back_each_new_receipt_and_source_conversion(self):
        self.options_for_split()
        with (
            patch(
                "core.membership_paid_visit.queue_confirmation",
                side_effect=ValidationError("fictional late failure"),
            ),
            self.assertRaises(ValidationError),
        ):
            self.buy_split()
        self.assertFalse(MembershipDraft.objects.exists())
        self.assertFalse(VisitMembershipConversion.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 1)
        self.assertEqual(total(self.original), Decimal("16.47"))

    def test_prepaid_uses_only_remaining_manual_split_and_needs_no_card(self):
        self.options_for_split(billing="prepaid")
        member = self.buy_split(
            self.options
            | dict(split={"cash": "10.00", "check": "10.00", "zelle": "10.00", "gift_card": "7.95"})
        )
        self.assertTrue(installment_paid(member.installments.first()))
        self.assertIsNone(member.billing_state.mandate_id)
        self.assertEqual(received(member.installments.first().invoice.sale), Decimal("37.95"))
        self.assertEqual(applied(member.installments.first().invoice.sale), Decimal("16.02"))
        self.assertEqual(member.installments.count(), 1)

    def test_deferred_guard_rejects_missing_verified_source_even_if_service_verification_bypassed(
        self,
    ):
        self.options_for_split()
        with self.assertRaisesMessage(DatabaseError, "complete conversion"), transaction.atomic():
            with patch("core.membership_first_split.verify"):
                self.buy_split(gift_card_verified=False)
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS core_paid_visit_purchase_complete IMMEDIATE")
        self.assertFalse(MembershipDraft.objects.exists())
        self.assertEqual(PaymentOperation.objects.count(), 1)

    def test_same_page_split_preview_and_confirmation_keep_paid_customer_and_sources(self):
        self.options_for_split()
        verified_owner_login(self.client, self.owner)
        values = self.web_values() | dict(
            expected_method="split",
            first_cash=".50",
            first_check=".50",
            first_zelle=".47",
            first_gift_card=".50",
            first_zelle_sender="Fictional bank sender",
            first_zelle_received_on=str(today() - timedelta(days=1)),
            first_gift_verified="on",
            first_zelle_verified="on",
        )
        preview = self.client.post(reverse("membership_offer"), values)
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(preview.json()["split_card_total"], "0.00")
        self.assertEqual(preview.json()["split_manual_total"], "1.97")
        values["reviewed"] = preview.json()["fingerprint"]
        saved = self.client.post(reverse("membership_purchase"), values)
        self.assertEqual(saved.status_code, 302, saved.content)
        member = VisitMembershipConversion.objects.get(booking=self.visit).purchase
        self.assert_complete(member)
