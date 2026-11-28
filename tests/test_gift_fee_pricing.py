"""Actual gift funds cover goods; partial cancellation keeps an eligible tender."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core.payments.amounts import COMPONENTS, ZERO, amount
from core.payments.checkout_pricing import line_components, tender_plan, visit_lines
from core.payments.credit_pricing import components, gift_limit
from core.payments.zelle import plan_with_prepayment
from core.pricing import Line
from tests import test_checkout_pricing as fixtures


@override_settings(APP_ENV="test")
class GiftFeePricingTests(SimpleTestCase):
    policy = fixtures.CheckoutPricingTests.policy

    def lines(self):
        return [
            Line("Child admissions", 1, Decimal("15"), True),
            Line("Partial cancellation fee", 1, Decimal("3"), False),
        ]

    def conserved(self, quote, plan):
        expected = line_components(quote)
        self.assertEqual(sum((amount(p["amount"]) for p in plan), ZERO), amount(quote["total"]))
        for part in plan:
            self.assertEqual(
                sum((row[key] for row in part["parts"] for key in COMPONENTS), ZERO),
                amount(part["amount"]),
            )
            self.assertTrue(all(row[key] >= ZERO for row in part["parts"] for key in COMPONENTS))
        for i, row in enumerate(expected):
            for key in COMPONENTS:
                self.assertEqual(sum((p["parts"][i][key] for p in plan), ZERO), row[key])
        for part in plan:
            if part["tender"] in {"gift_card", "credit"}:
                for i, line in enumerate(quote["lines"]):
                    if line["label"] in {"Cancellation fee", "Partial cancellation fee"}:
                        self.assertTrue(all(v == ZERO for v in part["parts"][i].values()))

    def test_whole_gift_choice_leaves_only_fee_and_its_nontaxable_card_fee(self):
        quote, plan = tender_plan(self.policy(), self.lines(), method="gift_card")
        self.assertEqual(
            [(p["tender"], p["amount"]) for p in plan], [("gift_card", "15.99"), ("card", "3.09")]
        )
        self.assertEqual(
            (
                quote["total"],
                quote["processing_fee"],
                quote["taxable_processing_fee"],
                quote["sales_tax"],
            ),
            ("19.08", "0.09", "0.00", "0.99"),
        )
        self.assertEqual(quote["card_funding"], ["0.00", "3.00"])
        self.conserved(quote, plan)

    def test_gift_and_cash_cover_goods_and_fee_without_any_card_charge(self):
        quote, plan = tender_plan(
            self.policy(), self.lines(), method="split", split={"cash": "3", "gift_card": "15.99"}
        )
        self.assertEqual(
            [(p["tender"], p["amount"]) for p in plan], [("gift_card", "15.99"), ("cash", "3.00")]
        )
        self.assertEqual(quote["total"], "18.99")
        self.assertEqual(quote["processing_fee"], "0.00")
        self.assertEqual(plan[1]["parts"][1]["net"], Decimal("3"))
        self.conserved(quote, plan)

    def test_credit_and_gift_share_the_same_goods_budget_before_cash(self):
        options = dict(
            method="split", split={"gift_card": "5.99", "cash": "3"}, credit=Decimal("10")
        )
        quote, plan = tender_plan(self.policy(), self.lines(), **options)
        self.assertEqual([p["tender"] for p in plan], ["credit", "gift_card", "cash"])
        self.assertEqual(gift_limit(quote, plan), Decimal("5.99"))
        self.conserved(quote, plan)
        with self.assertRaisesMessage(ValidationError, "Gift-card amount exceeds"):
            tender_plan(
                self.policy(),
                self.lines(),
                **(options | dict(split={"gift_card": "6", "cash": "2.99"})),
            )

    def test_gift_cannot_spend_the_fee_even_when_total_received_is_within_visit_total(self):
        with self.assertRaisesMessage(ValidationError, "Gift-card amount exceeds"):
            tender_plan(self.policy(), self.lines(), method="split", split={"gift_card": "16"})
        with self.assertRaisesMessage(ValidationError, "No admissions or socks remain"):
            tender_plan(self.policy(), self.lines()[1:], method="gift_card")
        with self.assertRaises(ValidationError):
            tender_plan(
                self.policy(),
                self.lines(),
                method="split",
                split=[("gift_card", "1")],
                credit=Decimal("1"),
            )

    def test_recorded_zelle_is_applied_once_before_gift_eligible_balance(self):
        quote, plan, applied = plan_with_prepayment(
            self.policy(), self.lines(), "gift_card", {}, Decimal("10")
        )
        self.assertEqual(applied, Decimal("10"))
        self.assertEqual(
            [(p["tender"], p["amount"]) for p in plan],
            [("zelle", "10.00"), ("gift_card", "7.57"), ("card", "1.46")],
        )
        self.assertTrue(plan[0]["advance"])
        self.assertEqual(gift_limit(quote, plan), Decimal("7.57"))
        self.assertEqual(quote["taxable_processing_fee"], "0.00")
        self.conserved(quote, plan)
        with self.assertRaisesMessage(ValidationError, "Record the new Zelle receipt first"):
            plan_with_prepayment(
                self.policy(),
                self.lines(),
                "split",
                {"gift_card": "1", "zelle": "1"},
                Decimal("10"),
            )

    def test_new_zelle_or_check_can_cover_the_fee_after_gift_covers_goods(self):
        for kind in ["check", "zelle"]:
            quote, plan = tender_plan(
                self.policy(), self.lines(), method="split", split={"gift_card": "15.99", kind: "3"}
            )
            self.assertEqual(plan[-1]["tender"], kind)
            self.assertEqual(plan[-1]["parts"][1]["net"], Decimal("3"))
            self.assertEqual(quote["processing_fee"], "0.00")
            self.conserved(quote, plan)

    def test_each_gift_cent_plus_cash_preserves_all_line_components_and_eligibility(self):
        for cents in range(1, 1600):
            quote, plan = tender_plan(
                self.policy(),
                self.lines(),
                method="split",
                split={"gift_card": str(Decimal(cents) / 100), "cash": "1"},
            )
            self.conserved(quote, plan)
            self.assertEqual(gift_limit(quote, plan), Decimal("15.99"))
        self.assertEqual(plan[-1]["parts"][1]["net"], Decimal("2"))
        self.assertEqual(plan[-1]["amount"], "2.06")

    def test_socks_keep_their_tax_exemption_and_new_fee_scope_reconstructs(self):
        lines = self.lines()
        lines.insert(1, Line("Grip socks — pick up upon arrival", 1, Decimal("1.99"), False))
        quote, plan = tender_plan(self.policy(), lines, method="gift_card")
        self.assertEqual(
            [(p["tender"], p["amount"]) for p in plan], [("gift_card", "17.98"), ("card", "3.09")]
        )
        self.assertEqual(
            (components(quote)[1]["item_tax"], components(quote)[1]["fee_tax"]), (0, 0)
        )
        self.conserved(quote, plan)

    def test_minimum_admission_and_supervised_goods_are_eligible_but_their_cancel_fee_is_not(self):
        for children, adults, babies, supervised in [
            (0, 1, 0, False),
            (0, 1, 1, False),
            (1, 0, 0, True),
        ]:
            lines = visit_lines(
                self.policy(),
                children=children,
                adults=adults,
                babies=babies,
                socks=0,
                supervised=supervised,
                fee_units=1,
            )
            quote, plan = tender_plan(self.policy(), lines, method="gift_card")
            self.assertEqual(plan[-1]["amount"], "3.09")
            self.conserved(quote, plan)
