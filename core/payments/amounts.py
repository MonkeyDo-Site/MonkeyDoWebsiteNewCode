"""Exact cents and deterministic allocation of an already accepted total."""

from decimal import ROUND_DOWN, Decimal, InvalidOperation

from django.core.exceptions import ValidationError

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
COMPONENTS = ("net", "fee", "item_tax", "fee_tax")


def amount(value):
    if isinstance(value, (bool, float)):
        raise ValidationError("Use exact decimal currency amounts.")
    try:
        result = Decimal(value)
        if not result.is_finite() or not ZERO <= result <= Decimal("999999999999.99"):
            raise ValueError
        if result.quantize(CENT) != result:
            raise ValueError
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Amounts must be nonnegative exact cents.") from None
    return result.quantize(CENT)


def allocate(total, weights):
    """Largest remainder, stable input-order tie breaking, no altered total tax."""
    total = amount(total)
    weights = [amount(w) for w in weights]
    combined = sum(weights, ZERO)
    if not combined:
        if total:
            raise ValidationError("Cannot allocate an amount without an eligible base.")
        return [ZERO for _ in weights]
    exact = [total * w / combined for w in weights]
    rounded = [x.quantize(CENT, rounding=ROUND_DOWN) for x in exact]
    remainder = int((total - sum(rounded, ZERO)) / CENT)
    order = sorted(range(len(weights)), key=lambda i: (-(exact[i] - rounded[i]), i))
    for i in order[:remainder]:
        rounded[i] += CENT
    return rounded
