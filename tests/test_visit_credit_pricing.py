"""Cancellation fees remain funded by actual tenders, including their own tax scope."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core.payments.amounts import COMPONENTS, ZERO, amount
from core.payments.checkout_pricing import line_components, tender_plan
from core.payments.credit_pricing import components, credit_limit
from core.payments.zelle import plan_with_prepayment
from core.pricing import Line
from tests import test_checkout_pricing as fixtures


@override_settings(APP_ENV="test")
class EligibleCreditPricingTests(SimpleTestCase):
    policy = fixtures.CheckoutPricingTests.policy

    def lines(self):
        return [
            Line("Child admissions", 1, Decimal("15"), True),
            Line("Partial cancellation fee", 1, Decimal("3"), False),
        ]

    def test_full_admission_credit_leaves_only_nontaxable_fee_on_card(self):
        quote, plan = tender_plan(
            self.policy(), self.lines(), method="card", credit=Decimal("15.99")
        )
        self.assertEqual(
            [(part["tender"], part["amount"]) for part in plan],
            [("credit", "15.99"), ("card", "3.09")],
        )
        self.assertEqual(
            (
                quote["processing_fee"],
                quote["taxable_processing_fee"],
                quote["sales_tax"],
                quote["total"],
            ),
            ("0.09", "0.00", "0.99", "19.08"),
        )
        self.assertTrue(all(value == ZERO for value in plan[0]["parts"][1].values()))
        self.assertEqual(line_components(quote)[1]["fee"], Decimal("0.09"))

    def test_partial_credit_computes_fee_tax_from_actual_remaining_taxable_card_base(self):
        quote, plan = tender_plan(
            self.policy(), self.lines(), method="card", credit=Decimal("10.00")
        )
        self.assertEqual(
            (
                plan[-1]["amount"],
                quote["processing_fee"],
                quote["taxable_processing_fee"],
                quote["sales_tax"],
            ),
            ("9.26", "0.26", "0.17", "1.00"),
        )
        self.assertEqual(quote["card_funding"], ["5.62", "3.00"])
        self.assertEqual(plan[0]["parts"][0]["item_tax"], Decimal("0.62"))
        # Socks keep their exemption while the card funds both goods classes.
        lines = self.lines()
        lines.insert(1, Line("Grip socks — pick up upon arrival", 1, Decimal("1.99"), False))
        quote, plan = tender_plan(self.policy(), lines, method="card", credit=Decimal("10.00"))
        self.assertEqual((quote["total"], plan[-1]["amount"]), ("21.31", "11.31"))
        self.assertEqual(
            (quote["processing_fee"], quote["taxable_processing_fee"]), ("0.32", "0.20")
        )
        self.assertEqual(
            (components(quote)[1]["item_tax"], components(quote)[1]["fee_tax"]), (0, 0)
        )

    def test_cash_and_recorded_bank_funds_are_not_credit_or_another_receipt(self):
        quote, plan = tender_plan(
            self.policy(), self.lines(), method="cash", credit=Decimal("15.99")
        )
        self.assertEqual(
            [(part["tender"], part["amount"]) for part in plan],
            [("credit", "15.99"), ("cash", "3.00")],
        )
        self.assertEqual(quote["total"], "18.99")
        self.assertEqual(
            credit_limit(self.policy(), self.lines(), Decimal("10.00")), Decimal("7.57")
        )
        quote, plan, bank = plan_with_prepayment(
            self.policy(), self.lines(), "card", {}, Decimal("10.00"), credit=Decimal("7.57")
        )
        self.assertEqual(
            [(part["tender"], part["amount"]) for part in plan],
            [("zelle", "10.00"), ("credit", "7.57"), ("card", "1.46")],
        )
        self.assertTrue(plan[0]["advance"])
        self.assertEqual(bank, 10)
        self.assertEqual(quote["sales_tax"], "0.99")
        with self.assertRaises(ValidationError):
            plan_with_prepayment(
                self.policy(), self.lines(), "card", {}, Decimal("10.00"), credit=Decimal("7.58")
            )

    def test_each_credit_cent_keeps_cancellation_and_components_within_their_funding(self):
        for cents in range(1, 1600):
            with self.subTest(cents=cents):
                quote, plan = tender_plan(
                    self.policy(),
                    self.lines(),
                    method="split",
                    split={"cash": "1.00"},
                    credit=Decimal(cents) / 100,
                )
                accepted = components(quote)
                self.assertEqual(
                    sum((amount(part["amount"]) for part in plan), ZERO), amount(quote["total"])
                )
                for i, line in enumerate(accepted):
                    for key in COMPONENTS:
                        self.assertEqual(
                            sum((part["parts"][i][key] for part in plan), ZERO), line[key]
                        )
                self.assertTrue(all(value == ZERO for value in plan[0]["parts"][1].values()))
                self.assertTrue(
                    all(
                        row[key] >= ZERO
                        for part in plan
                        for row in part["parts"]
                        for key in COMPONENTS
                    )
                )

    def test_unrecognized_or_tampered_component_scope_is_rejected(self):
        quote, _ = tender_plan(self.policy(), self.lines(), method="card", credit=Decimal("15.99"))
        for change in (
            {"component_allocation": "other"},
            {"card_funding": ["15.00"]},
            {"card_funding": ["15.00", "4.00"]},
            {"processing_fee": "0.90"},
            {"taxable_processing_fee": "0.09"},
        ):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                components(quote | change)
