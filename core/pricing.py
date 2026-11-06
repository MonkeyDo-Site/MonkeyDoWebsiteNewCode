"""Decimal-only test pricing. No membership allocation or provider operation."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError

CENT = Decimal("0.01")


def decimal(value):
    if isinstance(value, (float, bool)):
        raise ValidationError("Use exact decimal amounts.")
    try:
        number = Decimal(value)
    except Exception:
        raise ValidationError("Invalid decimal amount.") from None
    if not number.is_finite() or number < 0:
        raise ValidationError("Amounts must be finite and nonnegative.")
    return number


def money(value):
    return decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Line:
    label: str
    quantity: int
    unit_price: Decimal
    taxable: bool


def quote_lines(lines, policy, card_base=None):
    if settings.APP_ENV not in {"development", "test", "staging"}:
        raise ValidationError("Production pricing is not configured or approved.")
    items = []
    for line in lines:
        if type(line.quantity) is not int or line.quantity < 0:
            raise ValidationError("Quantities must be nonnegative integers.")
        unit = money(line.unit_price)
        amount = money(unit * line.quantity)
        items.append(
            {
                "label": line.label,
                "quantity": line.quantity,
                "unit_price": str(unit),
                "amount": str(amount),
                "taxable": bool(line.taxable),
            }
        )
    subtotal = sum((Decimal(item["amount"]) for item in items), Decimal(0))
    taxable = sum((Decimal(item["amount"]) for item in items if item["taxable"]), Decimal(0))
    base = subtotal if card_base is None else money(card_base)
    if base > subtotal:
        raise ValidationError("Card-funded base exceeds purchase subtotal.")
    fee = money(base * decimal(policy.card_fee_rate))
    taxable_fee = money(fee * taxable / subtotal) if subtotal else Decimal("0.00")
    tax = money((taxable + taxable_fee) * decimal(policy.tax_rate))
    rates = {
        name: str(getattr(policy, name))
        for name in (
            "child_price",
            "extra_adult_price",
            "minimum_admission",
            "supervised_price",
            "sock_price",
            "tax_rate",
            "card_fee_rate",
        )
    }
    return {
        "test_mode": True,
        "policy_id": policy.pk,
        "rates": rates,
        "lines": items,
        "subtotal": str(money(subtotal)),
        "taxable_subtotal": str(money(taxable)),
        "card_base": str(money(base)),
        "processing_fee": str(fee),
        "taxable_processing_fee": str(taxable_fee),
        "sales_tax": str(tax),
        "total": str(money(subtotal + fee + tax)),
    }


def validate_attendees(children, adults, babies, supervised=False, socks=0):
    if any(type(n) is not int or not 0 <= n <= 32767 for n in (children, adults, babies)):
        raise ValidationError(
            "Attendee counts must be nonnegative whole numbers supported by the booking record."
        )
    if type(socks) is not int or not 0 <= socks <= 2147483647:
        raise ValidationError("Socks must be a nonnegative whole number.")
    if not children + adults + babies:
        raise ValidationError("At least one attendee is required.")
    if supervised and (not children or adults or babies):
        raise ValidationError("Supervised play contains children only.")
    if not supervised and adults < 1:
        raise ValidationError("Accompanied play requires an adult.")


def booking_quote(
    policy, *, children, adults, babies, socks=0, supervised=False, expected_method="card"
):
    validate_attendees(children, adults, babies, supervised, socks)
    if expected_method not in {"card", "cash", "check", "zelle", "gift_card"}:
        raise ValidationError("Choose a supported expected payment method.")
    lines = []
    if supervised:
        lines.append(Line("Supervised child admissions", children, policy.supervised_price, True))
    elif children:
        lines.append(Line("Child admissions", children, policy.child_price, True))
    else:
        lines.append(
            Line(
                "Required baby admission" if babies else "Required adult admission",
                1,
                policy.minimum_admission,
                True,
            )
        )
    if not supervised and adults > 1:
        lines.append(Line("Additional adults", adults - 1, policy.extra_adult_price, True))
    if socks:
        lines.append(Line("Grip socks — pick up upon arrival", socks, policy.sock_price, False))
    result = quote_lines(lines, policy, card_base=None if expected_method == "card" else Decimal(0))
    result["expected_method"] = expected_method
    result["membership_benefits_applied"] = False
    return result
