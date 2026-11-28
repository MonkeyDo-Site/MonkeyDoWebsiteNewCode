"""Read-only cumulative price explanations reconcile to actual saved cents."""

import uuid
from decimal import Decimal

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.booking_estimates import edit_estimate
from core.models import BookingQuote, FinancialPosting, PaymentOperation
from core.payments.checkout import preview
from core.price_adjustments import booking_price_adjustment, compare_prices
from tests import test_booking_checkout as fixtures
from tests.helpers import verified_owner_login
from tests.test_owner_accounts import STORAGES


def quote(lines, fee="0", tax="0", **extra):
    subtotal = sum((Decimal(str(amount)) for label, quantity, amount in lines), Decimal("0"))
    return {
        "lines": [
            {
                "label": label,
                "quantity": quantity,
                "unit_price": str(Decimal(str(amount)) / quantity),
                "amount": str(amount),
            }
            for label, quantity, amount in lines
        ],
        "subtotal": str(subtotal),
        "processing_fee": fee,
        "sales_tax": tax,
        "total": str(subtotal + Decimal(fee) + Decimal(tax)),
        **extra,
    }


class AdjustmentArithmeticTests(SimpleTestCase):
    def reconciles(self, original, current):
        summary = compare_prices(original, current)
        self.assertEqual(
            summary["original_total"]
            + sum((row["delta"] for row in summary["rows"]), Decimal("0")),
            summary["total"],
        )
        return summary

    def test_supplied_arrival_example_separates_admission_fee_and_tax(self):
        old = quote(
            [
                ("Child admissions", 3, "45"),
                ("Additional adults", 1, "5"),
                ("Grip socks — pick up upon arrival", 1, "1.99"),
            ],
            tax="3.30",
        )
        new = quote(
            [
                ("Child admissions", 2, "30"),
                ("Additional adults", 1, "5"),
                ("Grip socks — pick up upon arrival", 1, "1.99"),
                ("Partial cancellation fee", 1, "3"),
            ],
            tax="2.31",
        )
        result = self.reconciles(old, new)
        self.assertEqual(result["original_total"], Decimal("55.29"))
        self.assertEqual(
            [(r["label"], r["delta"]) for r in result["rows"]],
            [
                ("Minus cancelled admissions", Decimal("-15")),
                ("Sales-tax adjustment", Decimal("-.99")),
                ("Plus cancellation fee (no sales tax)", Decimal("3")),
            ],
        )
        self.assertEqual(result["total"], Decimal("42.30"))

    def test_mixed_additions_and_removals_are_visible_when_the_net_is_zero(self):
        old = quote([("Child admissions", 1, "15"), ("Grip socks — pick up upon arrival", 2, "4")])
        new = quote([("Child admissions", 1, "15"), ("Additional adults", 1, "4")])
        summary = self.reconciles(old, new)
        self.assertEqual([r["delta"] for r in summary["rows"]], [Decimal("4"), Decimal("-4")])
        self.assertIn("adult admissions", summary["rows"][0]["label"])
        self.assertIn("socks", summary["rows"][1]["label"])

    def test_changed_admission_price_is_not_mislabeled_as_an_extra_child(self):
        old = quote([("Child admissions", 2, "30")])
        new = quote([("Supervised child admissions", 3, "56.97")], fee="1.71", tax="3.87")
        summary = self.reconciles(old, new)
        self.assertEqual(summary["rows"][0]["delta"], Decimal("18.99"))
        self.assertEqual(summary["rows"][1]["delta"], Decimal("7.98"))
        self.assertEqual(summary["rows"][1]["label"], "Admission/item price adjustment")

    def test_owner_price_uses_explicit_owner_adjustment_without_inventing_a_fee(self):
        old = quote(
            [
                ("Child admissions", 2, "30"),
                ("Additional adults", 1, "5"),
                ("Grip socks — pick up upon arrival", 1, "1.99"),
            ]
        )
        new = quote(
            [("Owner-priced admissions", 1, "20"), ("Grip socks — pick up upon arrival", 2, "3.98")]
        )
        summary = self.reconciles(old, new)
        self.assertEqual(summary["rows"][0]["label"], "Owner pricing adjustment")
        self.assertEqual(summary["rows"][0]["delta"], Decimal("-15"))
        self.assertFalse(any("cancellation" in r["label"] for r in summary["rows"]))

    def test_unchanged_or_missing_historical_quote_has_no_fabricated_comparison(self):
        original = quote([("Child admissions", 1, "15")])
        self.assertIsNone(compare_prices(original, original))
        self.assertIsNone(compare_prices({}, original))


@override_settings(
    BOOKING_COMPLETION_ENABLED=True,
    BOOKING_EMAIL_ENABLED=True,
    WAIVER_ENABLED=True,
    PAYMENT_SANDBOX_ENABLED=True,
    CUSTOMER_TEST_BOOKING=True,
    BANQUEST_API_SOURCE_KEY="fake-sandbox",
    STORAGES=STORAGES,
)
class AdjustmentWorkflowTests(TestCase):
    setUp = fixtures.CheckoutTests.setUp
    create = fixtures.CheckoutTests.create
    flow = fixtures.CheckoutTests.flow
    card = fixtures.CheckoutTests.card
    save_card = fixtures.CheckoutTests.save_card
    gateway = fixtures.CheckoutTests.gateway
    ready = fixtures.CheckoutTests.ready
    booking = fixtures.CheckoutTests.booking
    arrival_inputs = fixtures.CheckoutTests.arrival_inputs
    act = fixtures.CheckoutTests.act

    def test_arrival_and_edit_preview_share_first_saved_total_and_create_no_payments(self):
        booking = self.booking()
        original = booking.quotes.first()
        values = self.arrival_inputs(booking, children=2, method="card")
        live = preview(
            actor=self.staff,
            booking_id=booking.pk,
            kind="arrival",
            data=values,
            validate_waivers=False,
        )[2]
        data = {
            **values,
            "supervised": False,
            "expected_method": "card",
            "version": booking.edit_version,
            "session": booking.session,
        }
        edit = edit_estimate(booking, data)
        self.assertEqual(edit["adjustment"], booking_price_adjustment(booking, live))
        # A later immutable quote does not replace the original booked baseline.
        BookingQuote.objects.create(
            booking=booking, policy=original.policy, revision=2, snapshot=live, actor=self.owner
        )
        self.assertEqual(
            booking_price_adjustment(booking, live)["original_total"],
            Decimal(original.snapshot["total"]),
        )
        self.assertEqual(BookingQuote.objects.get(pk=original.pk).snapshot, original.snapshot)
        self.assertFalse(PaymentOperation.objects.exists())
        self.assertFalse(FinancialPosting.objects.exists())

    def test_saved_arrival_renders_one_adjusted_total_from_accepted_invoice(self):
        booking = self.booking()
        self.act(booking, self.arrival_inputs(booking, socks=1, method="cash"))
        verified_owner_login(self.client, self.owner)
        response = self.client.get(reverse("booking_detail", args=[booking.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Original booking total")
        self.assertContains(response, "Plus additional socks")
        self.assertContains(response, "Adjusted total", count=1)
        self.assertNotContains(response, "Actual total at arrival")

    def test_edited_preview_html_and_arrival_json_include_the_comparison_without_saving(self):
        booking = self.booking()
        verified_owner_login(self.client, self.owner)
        values = {
            "version": booking.edit_version,
            "children": 2,
            "adults": 1,
            "babies": 0,
            "socks": 0,
            "expected_method": "card",
            "session": booking.session_id,
        }
        response = self.client.post(reverse("booking_estimate", args=[booking.pk]), values)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("Original booking total", response.json()["html"])
        self.assertEqual(response.json()["html"].count("Adjusted total"), 1)
        values.update(request_key=uuid.uuid4(), method="card", waiver_confirmed="yes")
        response = self.client.post(
            reverse("booking_arrival", args=[booking.pk]), values, HTTP_ACCEPT="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("Original booking total", response.json()["html"])
        booking.refresh_from_db()
        self.assertEqual(booking.children, 1)
        self.assertFalse(booking.attendance)
        self.assertFalse(PaymentOperation.objects.exists())


class MemberAdjustmentTests(SimpleTestCase):
    def test_ordinary_quote_without_metadata_keeps_new_adult_allowance_out_of_cancellations(self):
        old = quote([("Child admissions", 1, "15"), ("Additional adults", 2, "10")])
        new = quote(
            [("Child admissions — Unlimited membership", 1, "0"), ("Additional adults", 1, "5")],
            membership_attendees={"adults": 3},
        )
        result = compare_prices(old, new)
        self.assertEqual(
            [(row["label"], row["delta"]) for row in result["rows"]],
            [("Membership benefit adjustment", Decimal("-20"))],
        )

    def test_ordinary_historical_quote_still_separates_an_actual_removed_adult(self):
        old = quote([("Child admissions", 1, "15"), ("Additional adults", 2, "10")])
        new = quote(
            [("Child admissions — Unlimited membership", 1, "0")],
            membership_attendees={"adults": 2},
        )
        result = compare_prices(old, new)
        self.assertEqual(
            [(row["label"], row["delta"]) for row in result["rows"]],
            [
                ("Minus cancelled adult admissions", Decimal("-5")),
                ("Membership benefit adjustment", Decimal("-20")),
            ],
        )

    def test_removing_one_paid_child_does_not_average_its_price_with_two_free_children(self):
        free = "Child admissions — Subscription free visits"
        old = quote([(free, 2, "0"), ("Child admissions", 1, "15")])
        new = quote([(free, 2, "0")])
        result = compare_prices(old, new)
        self.assertEqual(
            [(row["label"], row["delta"]) for row in result["rows"]],
            [("Minus cancelled admissions", Decimal("-15"))],
        )

    def test_applying_benefit_to_same_child_is_price_adjustment_not_cancellation(self):
        old = quote([("Child admissions", 1, "15")])
        new = quote([("Child admissions — Unlimited membership", 1, "0")])
        result = compare_prices(old, new)
        self.assertEqual(
            [(row["label"], row["delta"]) for row in result["rows"]],
            [("Membership benefit adjustment", Decimal("-15"))],
        )

    def test_stacked_adult_allowance_is_benefit_adjustment_when_no_adults_leave(self):
        old = quote(
            [
                ("Child admissions — Subscription free visits", 1, "0"),
                ("Additional adults", 1, "5"),
            ],
            membership_attendees={"adults": 3},
        )
        new = quote(
            [
                ("Child admissions — Subscription free visits", 1, "0"),
                ("Child admissions — Unlimited membership", 1, "0"),
            ],
            membership_attendees={"adults": 3},
        )
        result = compare_prices(old, new)
        self.assertEqual(
            [(row["label"], row["delta"]) for row in result["rows"]],
            [("Membership benefit adjustment", Decimal("-5"))],
        )

    def test_paid_admissions_are_removed_before_free_and_discounted_places(self):
        old = quote(
            [
                ("Child admissions — Subscription free visits", 2, "0"),
                ("Child admissions — Subscription additional visits", 1, "5.99"),
                ("Child admissions", 2, "30"),
            ]
        )
        new = quote(
            [
                ("Child admissions — Subscription free visits", 2, "0"),
                ("Child admissions — Subscription additional visits", 1, "5.99"),
            ]
        )
        result = compare_prices(old, new)
        self.assertEqual(
            [(row["label"], row["delta"]) for row in result["rows"]],
            [("Minus cancelled admissions", Decimal("-30"))],
        )
