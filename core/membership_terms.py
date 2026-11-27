"""Accepted owner-supplied membership terms, rendered with the actual purchase."""

from dataclasses import asdict

from .date_display import display_date
from .membership_benefits import CURRENT_RULES

VERSION = "MD-MEMBERSHIP-2026-01"


def rules_snapshot():
    return {
        key: str(value) if key.endswith(("price", "discount")) else value
        for key, value in asdict(CURRENT_RULES).items()
    }


def terms(
    *,
    kind,
    starts_on,
    months,
    billing,
    minimum_override=False,
    comped=False,
    renewal=False,
    minimum_months=3,
):
    opening = f"Your membership begins on {display_date(starts_on, 'F j, Y')} and continues for {months} months."
    minimum = (
        "This qualifying renewal does not require a new three-month minimum."
        if renewal and minimum_months == 1
        else "The owner has approved this shorter initial term."
        if (minimum_override or comped) and months < 3
        else "New memberships require a minimum initial term of three months."
    )
    payment = (
        "This membership is complimentary. No payment is required."
        if comped
        else "If you select monthly billing, the saved payment method will be charged monthly automatically, starting from today."
        if billing == "monthly"
        else "The full selected membership term is paid at purchase."
    )
    product = (
        "Each Subscription place includes two free ordinary child visits per membership month, then $5.99 additional visits. Two free adults are included when Subscription benefits apply. Unused free visits do not roll over to the next month. Members enjoy 25% off on supervised play visits and a 15% discount on parties."
        if kind == "subscription"
        else "Each Unlimited place includes one free ordinary child visit per New York calendar day. Two free adults are included when Unlimited benefits apply. Members enjoy a 15% discount on parties. Supervised play and Chol Hamoed visits are excluded from membership benefits. Members can book supervised play and Chol Hamoed visits at full price."
    )
    cancellation = (
        "For cancellation, please call or text MonkeyDo."
        if renewal and minimum_months == 1
        else "This owner-approved shorter membership covers the selected fixed term."
        if (minimum_override or comped) and months < 3
        else "Membership cannot be cancelled during the initial three month term."
    )
    return " ".join(
        [
            opening,
            minimum,
            payment,
            "Cancellation and no-show fees apply to all visits booked with membership benefits.",
            product,
            "Membership can be renewed after the membership ends. Membership that is renewed one week past the membership end date is subject to a three month minimum. Membership renewed within a week has no monthly minimum.",
            cancellation,
            "The selected term ends without automatic renewal. Scheduled installments only complete the membership term purchased.",
        ]
    )
