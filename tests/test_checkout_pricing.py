"""Actual-inclusive split tender and deterministic tax/fee reconciliation."""

from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core.payments.amounts import COMPONENTS, ZERO, amount
from core.payments.checkout_pricing import tender_plan
from core.pricing import Line


@override_settings(APP_ENV="test")
class CheckoutPricingTests(SimpleTestCase):
    def policy(self, **changes):
        return SimpleNamespace(
            pk=1,
            child_price=Decimal("15"),
            extra_adult_price=Decimal("5"),
            minimum_admission=Decimal("15"),
            supervised_price=Decimal("18.99"),
            sock_price=Decimal("1.99"),
            tax_rate=Decimal(".066"),
            card_fee_rate=Decimal(".03"),
            **changes,
        )

    def test_accountant_proportional_example_uses_actual_25_99_cash_not_25_pretax(self):
        quote, plan = tender_plan(
            self.policy(),
            [Line("Taxable", 1, Decimal("30"), True), Line("Exempt", 1, Decimal("20"), False)],
            method="split",
            split={"cash": "25.99"},
        )
        self.assertEqual(quote["subtotal"], "50.00")
        self.assertEqual(quote["processing_fee"], "0.75")
        self.assertEqual(quote["sales_tax"], "2.01")
        self.assertEqual(quote["total"], "52.76")
        self.assertEqual(
            [(p["tender"], p["amount"]) for p in plan], [("cash", "25.99"), ("card", "26.77")]
        )
        self.assertEqual(sum((part["net"] for part in plan[0]["parts"]), ZERO), Decimal("25"))
        self.assertTrue(
            all(part["fee"] == ZERO and part["fee_tax"] == ZERO for part in plan[0]["parts"])
        )

    def test_each_fixed_cash_cent_reconciles_mixed_items_without_adding_card_fee_to_cash(self):
        lines = [Line("Taxable", 1, Decimal("15"), True), Line("Exempt", 1, Decimal("1.99"), False)]
        policy = self.policy()
        for cents in range(1, 1799):
            value = Decimal(cents) / 100
            quote, plan = tender_plan(policy, lines, method="split", split={"cash": str(value)})
            self.assertEqual(amount(plan[0]["amount"]), value)
            self.assertEqual(sum((amount(p["amount"]) for p in plan), ZERO), amount(quote["total"]))
            for p in plan:
                self.assertEqual(
                    sum((part[k] for part in p["parts"] for k in COMPONENTS), ZERO),
                    amount(p["amount"]),
                )
                self.assertTrue(all(part[k] >= ZERO for part in p["parts"] for k in COMPONENTS))
            self.assertTrue(
                all(part["fee"] == ZERO and part["fee_tax"] == ZERO for part in plan[0]["parts"])
            )

    def test_multiple_received_tenders_and_card_balance_reconcile_without_item_selection(self):
        quote, plan = tender_plan(
            self.policy(),
            [Line("Taxable", 3, Decimal("15"), True)],
            method="split",
            split={"cash": "10.00", "gift_card": "20.00"},
        )
        self.assertEqual([p["tender"] for p in plan], ["cash", "gift_card", "card"])
        self.assertEqual(sum((amount(p["amount"]) for p in plan), ZERO), amount(quote["total"]))
        with self.assertRaises(ValidationError):
            tender_plan(
                self.policy(),
                [Line("Taxable", 1, Decimal("15"), True)],
                method="split",
                split={"cash": "20.00"},
            )
