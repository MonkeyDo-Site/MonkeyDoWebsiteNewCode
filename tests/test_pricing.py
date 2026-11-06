from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings

from core.models import PricingPolicy
from core.pricing import Line, booking_quote, quote_lines


class PricingTests(TestCase):
    def setUp(self):
        self.policy = PricingPolicy.objects.first()

    def test_approved_full_card_regression_examples(self):
        cases = [
            ([Line("Admissions", 2, Decimal("15"), True)], ("30.00", "0.90", "2.04", "32.94")),
            (
                [Line("Subscription", 1, Decimal("17.99"), False)],
                ("17.99", "0.54", "0.00", "18.53"),
            ),
            (
                [
                    Line("Admission", 1, Decimal("15"), True),
                    Line("Socks", 1, Decimal("1.99"), False),
                ],
                ("16.99", "0.51", "1.02", "18.52"),
            ),
            (
                [
                    Line("Subscriptions", 2, Decimal("17.99"), False),
                    Line("Remaining admission after benefits", 1, Decimal("15"), True),
                ],
                ("50.98", "1.53", "1.02", "53.53"),
            ),
            (
                [
                    Line("Subscriptions", 2, Decimal("17.99"), False),
                    Line("Remaining admissions after benefits", 3, Decimal("15"), True),
                ],
                ("80.98", "2.43", "3.06", "86.47"),
            ),
            (
                [Line("Physical gift-card sale", 1, Decimal("100"), False)],
                ("100.00", "3.00", "0.00", "103.00"),
            ),
            (
                [Line("Discounted party", 1, Decimal("245.65"), True)],
                ("245.65", "7.37", "16.70", "269.72"),
            ),
        ]
        for lines, expected in cases:
            with self.subTest(expected=expected):
                result = quote_lines(lines, self.policy)
                self.assertEqual(
                    tuple(
                        result[key] for key in ("subtotal", "processing_fee", "sales_tax", "total")
                    ),
                    expected,
                )

    def test_proportional_card_funded_base_and_no_fee_on_tax(self):
        lines = [
            Line("Taxable", 1, Decimal("30"), True),
            Line("Nontaxable", 1, Decimal("20"), False),
        ]
        result = quote_lines(lines, self.policy, card_base=Decimal("25"))
        self.assertEqual(result["processing_fee"], "0.75")
        self.assertEqual(result["taxable_processing_fee"], "0.45")
        self.assertEqual(result["sales_tax"], "2.01")
        self.assertEqual(result["total"], "52.76")

    def test_cash_and_zero_subtotal(self):
        result = quote_lines([Line("Admission", 1, Decimal("15"), True)], self.policy, card_base=0)
        self.assertEqual(
            (result["processing_fee"], result["sales_tax"], result["total"]),
            ("0.00", "0.99", "15.99"),
        )
        self.assertEqual(quote_lines([], self.policy)["total"], "0.00")

    def test_ordinary_baby_only_and_adult_only_pricing(self):
        cases = [(2, 2, 1, "35.00"), (0, 1, 2, "15.00"), (0, 3, 0, "25.00"), (0, 2, 1, "20.00")]
        for children, adults, babies, subtotal in cases:
            with self.subTest(children=children, adults=adults, babies=babies):
                result = booking_quote(
                    self.policy,
                    children=children,
                    adults=adults,
                    babies=babies,
                    expected_method="cash",
                )
                self.assertEqual(result["subtotal"], subtotal)

    def test_supervised_and_staff_sock_quantities(self):
        result = booking_quote(
            self.policy, children=2, adults=0, babies=0, supervised=True, socks=40
        )
        self.assertEqual(result["subtotal"], "117.58")
        self.assertEqual(result["taxable_subtotal"], "37.98")
        self.assertFalse(result["membership_benefits_applied"])

    def test_invalid_counts_and_decimal_values_rejected(self):
        for args in (
            {"children": 1, "adults": 0, "babies": 0},
            {"children": True, "adults": 1, "babies": 0},
            {"children": 0, "adults": 0, "babies": 0},
        ):
            with self.assertRaises(ValidationError):
                booking_quote(self.policy, **args)
        for value in (float("inf"), Decimal("NaN"), Decimal("-1")):
            with self.assertRaises(ValidationError):
                quote_lines([Line("Bad", 1, value, True)], self.policy)
        with self.assertRaises(ValidationError):
            quote_lines(
                [Line("Admission", 1, Decimal("15"), True)], self.policy, card_base=Decimal("16")
            )

    @override_settings(APP_ENV="production")
    def test_staging_rate_is_never_used_in_production(self):
        with self.assertRaises(ValidationError):
            quote_lines([], self.policy)

    def test_policy_is_immutable_through_model_queryset_and_sql(self):
        with self.assertRaises(ValidationError):
            self.policy.save()
        with self.assertRaises(ValidationError):
            PricingPolicy.objects.all().update(child_price=1)
        with self.assertRaises(ValidationError):
            self.policy.delete()
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE core_pricingpolicy SET child_price = 1 WHERE id = %s", [self.policy.pk]
                )
