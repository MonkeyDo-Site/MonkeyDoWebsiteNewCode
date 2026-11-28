"""Pure membership pricing plan. Persistence and reservation locks belong to callers.

Only trusted services build Place inputs from accepted cohorts, current payment
state and reservations for the appointment's actual month/day. A preview never
reserves or consumes a benefit and cannot activate an unpaid membership.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError

from .payments.checkout_pricing import visit_lines
from .pricing import Line, money, validate_attendees


@dataclass(frozen=True)
class BenefitRules:
    version: str = "MD-MEMBERSHIP-BENEFITS-2026-01"
    subscription_free_visits: int = 2
    subscription_additional_price: Decimal = Decimal("5.99")
    subscription_supervised_discount: Decimal = Decimal("0.25")
    adults_per_type: int = 2
    party_discount: Decimal = Decimal("0.15")


CURRENT_RULES = BenefitRules()


@dataclass(frozen=True)
class Place:
    """One anonymous purchased place, never a named-child entitlement."""

    membership_id: int
    number: int
    kind: str
    starts_on: date
    ends_on: date
    cycle_starts_on: date
    cycle_ends_on: date
    payments_current: bool
    free_visits_used: int = 0
    daily_used: bool = False
    rules: BenefitRules = CURRENT_RULES

    def validate(self):
        if any(type(value) is not int or value < 1 for value in (self.membership_id, self.number)):
            raise ValidationError("Use a valid membership and anonymous place number.")
        if self.kind not in {"subscription", "unlimited"}:
            raise ValidationError("Choose an accepted membership type.")
        dates = (self.starts_on, self.ends_on, self.cycle_starts_on, self.cycle_ends_on)
        if any(type(value) is not date for value in dates) or not (
            self.starts_on <= self.cycle_starts_on <= self.cycle_ends_on <= self.ends_on
        ):
            raise ValidationError("Use the accepted term and appointment-month boundaries.")
        if type(self.payments_current) is not bool or type(self.daily_used) is not bool:
            raise ValidationError("Use verified payment and daily-benefit state.")
        rules = self.rules
        if not isinstance(rules, BenefitRules) or not rules.version:
            raise ValidationError("Use the accepted benefit rules.")
        if (
            type(rules.subscription_free_visits) is not int
            or rules.subscription_free_visits < 0
            or type(rules.adults_per_type) is not int
            or rules.adults_per_type < 0
            or type(self.free_visits_used) is not int
            or not 0 <= self.free_visits_used <= rules.subscription_free_visits
            or not isinstance(rules.subscription_additional_price, Decimal)
            or not rules.subscription_additional_price.is_finite()
            or rules.subscription_additional_price < 0
            or any(
                not isinstance(value, Decimal) or not value.is_finite() or not 0 <= value <= 1
                for value in (rules.subscription_supervised_discount, rules.party_discount)
            )
        ):
            raise ValidationError("Use valid accepted benefit limits and prices.")

    @property
    def identity(self):
        return self.membership_id, self.number

    def eligible(self, appointment_on):
        return (
            self.payments_current
            and self.starts_on <= appointment_on <= self.ends_on
            and self.cycle_starts_on <= appointment_on <= self.cycle_ends_on
        )


@dataclass(frozen=True)
class BenefitUse:
    membership_id: int
    place: int
    kind: str
    appointment_on: date
    cycle_starts_on: date
    cycle_ends_on: date
    price: Decimal
    rules_version: str

    @property
    def consumes_free_visit(self):
        return self.kind in {"unlimited_daily", "subscription_free"}

    def snapshot(self):
        return {
            "membership_id": self.membership_id,
            "place": self.place,
            "kind": self.kind,
            "appointment_on": self.appointment_on.isoformat(),
            "cycle_starts_on": self.cycle_starts_on.isoformat(),
            "cycle_ends_on": self.cycle_ends_on.isoformat(),
            "price": str(self.price),
            "rules_version": self.rules_version,
        }


@dataclass(frozen=True)
class BenefitPlan:
    lines: tuple[Line, ...]
    uses: tuple[BenefitUse, ...]
    free_adults: int
    ordinary_children: int
    chol_hamoed: bool
    owner_price_review: bool = False

    def snapshot(self):
        return {
            "uses": [use.snapshot() for use in self.uses],
            "free_adults": self.free_adults,
            "ordinary_children": self.ordinary_children,
            "chol_hamoed": self.chol_hamoed,
            "owner_price_review": self.owner_price_review,
        }


def plan_visit(
    policy,
    places,
    *,
    appointment_on,
    children,
    adults,
    babies=0,
    socks=0,
    supervised=False,
    chol_hamoed=False,
    special_admissions=None,
    comped=False,
):
    """Price a prospective visit without changing accepted bookings or usage.

    Ordinary order: Unlimited daily, Subscription free, Subscription additional,
    ordinary admission. A place can apply to at most one child in this booking.
    Current reservations are included by the trusted caller in used counts.
    """
    validate_attendees(children, adults, babies, supervised, socks)
    if type(appointment_on) is not date or any(
        type(value) is not bool for value in (supervised, chol_hamoed, comped)
    ):
        raise ValidationError("Use the New York appointment date and explicit visit choices.")
    if comped and special_admissions is not None:
        raise ValidationError("Choose complimentary or custom admissions pricing.")
    all_places = tuple(places)
    seen = set()
    for place in all_places:
        if not isinstance(place, Place):
            raise ValidationError("Use accepted membership places.")
        place.validate()
        if place.identity in seen:
            raise ValidationError("Each anonymous membership place can appear only once.")
        seen.add(place.identity)
    eligible = tuple(place for place in all_places if place.eligible(appointment_on))
    if comped or special_admissions is not None:
        lines = visit_lines(
            policy,
            children=children,
            adults=adults,
            babies=babies,
            socks=socks,
            supervised=supervised,
            special_admissions=special_admissions,
        )
        if comped:
            lines = [
                Line(line.label, line.quantity, Decimal("0.00"), line.taxable) for line in lines
            ]
        return BenefitPlan(
            tuple(lines),
            (),
            1 if not supervised else 0,
            children,
            chol_hamoed,
            owner_price_review=bool(eligible and not comped),
        )

    uses = []
    applied_places = []

    def use(place, kind, price):
        if len(uses) < children:
            uses.append(
                BenefitUse(
                    place.membership_id,
                    place.number,
                    kind,
                    appointment_on,
                    place.cycle_starts_on,
                    place.cycle_ends_on,
                    money(price),
                    place.rules.version,
                )
            )
            applied_places.append(place)

    subscriptions = sorted(
        (place for place in eligible if place.kind == "subscription"),
        key=lambda place: (place.cycle_ends_on, place.ends_on, place.membership_id, place.number),
    )
    if supervised:
        for place in subscriptions:
            use(
                place,
                "subscription_supervised",
                policy.supervised_price
                * (Decimal("1") - place.rules.subscription_supervised_discount),
            )
    else:
        if not chol_hamoed:
            for place in sorted(
                (place for place in eligible if place.kind == "unlimited" and not place.daily_used),
                key=lambda place: (place.ends_on, place.membership_id, place.number),
            ):
                use(place, "unlimited_daily", Decimal("0.00"))
        free = tuple(
            place
            for place in subscriptions
            if place.free_visits_used < place.rules.subscription_free_visits
        )
        additional = tuple(
            place
            for place in subscriptions
            if place.free_visits_used == place.rules.subscription_free_visits
        )
        for place in free:
            use(place, "subscription_free", Decimal("0.00"))
        for place in additional:
            use(place, "subscription_additional", place.rules.subscription_additional_price)

    if not uses:
        return BenefitPlan(
            tuple(
                visit_lines(
                    policy,
                    children=children,
                    adults=adults,
                    babies=babies,
                    socks=socks,
                    supervised=supervised,
                )
            ),
            (),
            0 if supervised else 1,
            children,
            chol_hamoed,
        )
    free_adults = 0
    if not supervised:
        # Places of the same type do not multiply the allowance. Different
        # applying types stack; use the accepted allowance for that type.
        for kind in {place.kind for place in applied_places}:
            free_adults += max(
                place.rules.adults_per_type for place in applied_places if place.kind == kind
            )
    labels = {
        "unlimited_daily": "Child admissions — Unlimited membership",
        "subscription_free": "Child admissions — Subscription free visits",
        "subscription_additional": "Child admissions — Subscription additional visits",
        "subscription_supervised": "Supervised child admissions — Subscription discount",
    }
    grouped = {}
    for item in uses:
        key = item.kind, item.price
        grouped[key] = grouped.get(key, 0) + 1
    lines = [
        Line(labels[kind], quantity, price, True) for (kind, price), quantity in grouped.items()
    ]
    remaining = children - len(uses)
    if remaining:
        lines.append(
            Line(
                "Supervised child admissions" if supervised else "Child admissions",
                remaining,
                policy.supervised_price if supervised else policy.child_price,
                True,
            )
        )
    if adults > free_adults:
        lines.append(
            Line("Additional adults", adults - free_adults, policy.extra_adult_price, True)
        )
    if socks:
        lines.append(Line("Grip socks — pick up upon arrival", socks, policy.sock_price, False))
    return BenefitPlan(tuple(lines), tuple(uses), free_adults, remaining, chol_hamoed)
