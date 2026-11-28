"""Accepted member-visit examples and boundary rules, without any DB mutation."""

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core.membership_benefits import BenefitRules, Place, plan_visit
from core.pricing import quote_lines


@override_settings(APP_ENV="test")
class MembershipBenefitTests(SimpleTestCase):
    def setUp(self):
        self.policy = SimpleNamespace(
            pk=1,
            child_price=Decimal("15.00"),
            minimum_admission=Decimal("15.00"),
            extra_adult_price=Decimal("5.00"),
            supervised_price=Decimal("18.99"),
            sock_price=Decimal("1.99"),
            card_fee_rate=Decimal("0.03"),
            tax_rate=Decimal("0.066"),
        )
        self.day = date(2026, 11, 23)
        self.subscription = Place(
            1,
            1,
            "subscription",
            date(2026, 11, 5),
            date(2027, 2, 4),
            date(2026, 11, 5),
            date(2026, 12, 4),
            True,
        )
        self.subscriptions = [self.subscription, replace(self.subscription, number=2)]
        self.unlimited = replace(self.subscription, membership_id=2, kind="unlimited")

    def plan(self, places=(), **changes):
        values = dict(appointment_on=self.day, children=1, adults=1)
        return plan_visit(self.policy, places, **(values | changes))

    def total(self, result, card=False):
        return Decimal(
            quote_lines(result.lines, self.policy, card_base=None if card else Decimal("0"))[
                "total"
            ]
        )

    def subtotal(self, result):
        return sum((line.unit_price * line.quantity for line in result.lines), Decimal("0"))

    def test_approved_mixed_membership_examples(self):
        cases = [
            (self.subscriptions + [self.unlimited], 4, 2, "15.00"),
            (
                [replace(place, free_visits_used=1) for place in self.subscriptions]
                + [self.unlimited],
                3,
                3,
                "0.00",
            ),
            (
                [replace(place, free_visits_used=2) for place in self.subscriptions]
                + [self.unlimited],
                4,
                2,
                "26.98",
            ),
            (self.subscriptions + [replace(self.unlimited, daily_used=True)], 3, 2, "15.00"),
        ]
        for places, children, adults, expected in cases:
            with self.subTest(expected=expected, children=children):
                self.assertEqual(
                    self.subtotal(self.plan(places, children=children, adults=adults)),
                    Decimal(expected),
                )

    def test_two_subscription_places_cannot_cover_four_children_in_one_booking(self):
        result = self.plan(self.subscriptions, children=4, adults=2)
        self.assertEqual(self.subtotal(result), Decimal("30"))
        self.assertEqual(len(result.uses), 2)
        self.assertEqual(result.ordinary_children, 2)

    def test_unlimited_benefits_are_used_before_subscription_free_visits(self):
        result = self.plan(self.subscriptions + [self.unlimited], children=1)
        self.assertEqual([use.kind for use in result.uses], ["unlimited_daily"])

    def test_soonest_expiring_free_subscription_benefit_is_used_first(self):
        earlier = replace(self.subscription, membership_id=3, cycle_ends_on=date(2026, 11, 28))
        result = self.plan([self.subscription, earlier])
        self.assertEqual(result.uses[0].membership_id, 3)

    def test_subscription_free_is_used_before_additional_discounted_admission(self):
        earlier_used = replace(
            self.subscription, membership_id=3, free_visits_used=2, cycle_ends_on=date(2026, 11, 28)
        )
        result = self.plan([earlier_used, self.subscription])
        self.assertEqual(result.uses[0].kind, "subscription_free")
        self.assertEqual(result.uses[0].membership_id, 1)

    def test_multiple_places_do_not_multiply_same_type_adult_allowance(self):
        result = self.plan(self.subscriptions, children=2, adults=4)
        self.assertEqual(result.free_adults, 2)
        self.assertEqual(self.subtotal(result), Decimal("10"))

    def test_applying_both_types_stacks_to_four_free_adults(self):
        result = self.plan(self.subscriptions + [self.unlimited], children=2, adults=5)
        self.assertEqual(result.free_adults, 4)
        self.assertEqual(self.subtotal(result), Decimal("5"))

    def test_a_type_that_does_not_apply_adds_no_adult_allowance(self):
        result = self.plan(self.subscriptions + [self.unlimited], children=1, adults=3)
        self.assertEqual(result.free_adults, 2)
        self.assertEqual(self.subtotal(result), Decimal("5"))

    def test_used_unlimited_day_returns_to_ordinary_adults_and_price(self):
        result = self.plan([replace(self.unlimited, daily_used=True)], children=2, adults=2)
        self.assertEqual(result.uses, ())
        self.assertEqual(result.free_adults, 1)
        self.assertEqual(self.subtotal(result), Decimal("35"))

    def test_chol_hamoed_excludes_unlimited_but_keeps_subscription(self):
        result = self.plan(
            self.subscriptions + [self.unlimited], children=4, adults=5, chol_hamoed=True
        )
        self.assertEqual(self.subtotal(result), Decimal("45"))
        self.assertEqual(result.free_adults, 2)
        self.assertTrue(all(use.kind == "subscription_free" for use in result.uses))
        ordinary = self.plan([self.unlimited], children=1, adults=2, chol_hamoed=True)
        self.assertEqual(self.subtotal(ordinary), Decimal("20"))

    def test_supervised_subscription_discount_does_not_consume_ordinary_free_visits(self):
        result = self.plan(
            [replace(place, free_visits_used=2) for place in self.subscriptions] + [self.unlimited],
            children=3,
            adults=0,
            supervised=True,
        )
        self.assertEqual(self.subtotal(result), Decimal("47.47"))
        self.assertTrue(
            all(
                use.price == Decimal("14.24") and not use.consumes_free_visit for use in result.uses
            )
        )
        self.assertEqual(result.free_adults, 0)

    def test_supervised_unlimited_has_no_discount(self):
        self.assertEqual(
            self.subtotal(self.plan([self.unlimited], children=1, adults=0, supervised=True)),
            Decimal("18.99"),
        )

    def test_socks_stay_nontaxable_when_admission_is_free(self):
        result = self.plan([self.subscription], socks=1)
        self.assertEqual(self.total(result, card=True), Decimal("2.05"))
        self.assertFalse(result.lines[-1].taxable)

    def test_overdue_or_initially_unpaid_membership_supplies_no_benefits(self):
        result = self.plan([replace(self.subscription, payments_current=False)])
        self.assertEqual(self.subtotal(result), Decimal("15"))
        self.assertFalse(result.uses)

    def test_appointment_date_selects_membership_window_not_booking_creation_date(self):
        future = replace(
            self.subscription,
            starts_on=date(2026, 12, 10),
            ends_on=date(2027, 3, 9),
            cycle_starts_on=date(2026, 12, 10),
            cycle_ends_on=date(2027, 1, 9),
        )
        self.assertFalse(self.plan([future], appointment_on=date(2026, 12, 9)).uses)
        self.assertEqual(
            self.total(self.plan([future], appointment_on=date(2026, 12, 10))), Decimal("0")
        )
        self.assertFalse(self.plan([future], appointment_on=date(2027, 3, 10)).uses)

    def test_future_cycle_with_current_required_payments_can_be_planned(self):
        future_cycle = replace(
            self.subscription, cycle_starts_on=date(2026, 12, 5), cycle_ends_on=date(2027, 1, 4)
        )
        self.assertEqual(
            self.total(self.plan([future_cycle], appointment_on=date(2026, 12, 8))), Decimal("0")
        )

    def test_no_free_visit_rollover_from_another_cycle(self):
        self.assertFalse(self.plan([self.subscription], appointment_on=date(2026, 12, 5)).uses)

    def test_baby_only_and_adult_only_visits_preserve_required_admission(self):
        for babies in (0, 1):
            with self.subTest(babies=babies):
                result = self.plan(self.subscriptions, children=0, adults=2, babies=babies)
                self.assertEqual(self.subtotal(result), Decimal("20"))
                self.assertFalse(result.uses)

    def test_comped_booking_consumes_no_member_benefit(self):
        result = self.plan(self.subscriptions, children=2, adults=3, socks=2, comped=True)
        self.assertEqual(self.total(result, card=True), Decimal("0"))
        self.assertFalse(result.uses)

    def test_owner_special_price_is_retained_for_explicit_review(self):
        result = self.plan(
            self.subscriptions, children=2, adults=3, special_admissions=Decimal("20")
        )
        self.assertEqual(self.subtotal(result), Decimal("20"))
        self.assertTrue(result.owner_price_review)
        self.assertFalse(result.uses)

    def test_accepted_member_prices_are_not_replaced_by_new_ordinary_prices(self):
        self.policy.child_price = Decimal("25")
        result = self.plan([replace(self.subscription, free_visits_used=2)], children=2)
        self.assertEqual(self.subtotal(result), Decimal("30.99"))

    def test_distinct_accepted_benefit_versions_keep_their_prices(self):
        old = replace(self.subscription, free_visits_used=2)
        new = replace(
            old,
            membership_id=3,
            rules=BenefitRules(
                version="review-fixture-new", subscription_additional_price=Decimal("6.50")
            ),
        )
        result = self.plan([old, new], children=2)
        self.assertEqual(self.subtotal(result), Decimal("12.49"))
        self.assertEqual(
            {use.rules_version for use in result.uses}, {old.rules.version, new.rules.version}
        )

    def test_duplicate_place_input_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.plan([self.subscription, self.subscription])

    def test_preview_does_not_change_or_consume_input(self):
        first = self.plan(self.subscriptions, children=2)
        self.assertEqual(first.snapshot(), self.plan(self.subscriptions, children=2).snapshot())
        self.assertEqual([place.free_visits_used for place in self.subscriptions], [0, 0])

    def test_invalid_usage_and_non_civil_dates_are_rejected(self):
        for value in (-1, 3, True):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.plan([replace(self.subscription, free_visits_used=value)])
        with self.assertRaises(ValidationError):
            self.plan(appointment_on=datetime(2026, 11, 23))

    def test_ineligible_public_attendee_shapes_remain_invalid(self):
        for changes in (
            {"adults": 0},
            {"children": 0, "adults": 0},
            {"supervised": True, "adults": 1},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.plan(self.subscriptions, **changes)
