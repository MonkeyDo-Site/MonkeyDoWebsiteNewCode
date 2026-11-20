"""Actual inclusive tenders, proportional base allocation and exact line cents."""

from decimal import Decimal

from django.core.exceptions import ValidationError

from core.pricing import Line, booking_quote, money, quote_lines

from .amounts import COMPONENTS, ZERO, allocate, amount

NONCARD = ("cash", "check", "zelle", "gift_card")


def visit_lines(policy, *, children, adults, babies, socks, supervised, fee_units=0):
    quote = booking_quote(
        policy,
        children=children,
        adults=adults,
        babies=babies,
        socks=socks,
        supervised=supervised,
        expected_method="cash",
    )
    lines = [
        Line(row["label"], row["quantity"], Decimal(row["unit_price"]), row["taxable"])
        for row in quote["lines"]
    ]
    if type(fee_units) is not int or fee_units < 0:
        raise ValidationError("Cancellation units must be nonnegative integers.")
    if fee_units:
        lines.append(Line("Partial cancellation fee", fee_units, Decimal("3.00"), False))
    return lines


def line_components(quote):
    lines = quote["lines"]
    taxable_fees = allocate(
        amount(quote["taxable_processing_fee"]),
        [row["amount"] if row["taxable"] else ZERO for row in lines],
    )
    exempt_fees = allocate(
        amount(quote["processing_fee"]) - amount(quote["taxable_processing_fee"]),
        [row["amount"] if not row["taxable"] else ZERO for row in lines],
    )
    weights = []
    for row, fee in zip(lines, taxable_fees):
        weights.extend([amount(row["amount"]) if row["taxable"] else ZERO, fee])
    taxes = allocate(amount(quote["sales_tax"]), weights)
    return [
        {
            "net": amount(row["amount"]),
            "fee": taxable_fees[i] + exempt_fees[i],
            "item_tax": taxes[2 * i],
            "fee_tax": taxes[2 * i + 1],
        }
        for i, row in enumerate(lines)
    ]


def tender_plan(policy, lines, *, method, split=None):
    """Fixed noncard values are amounts received, not silently treated as pretax."""
    if method not in {"card", "split", *NONCARD}:
        raise ValidationError("Choose the actual payment method.")
    cash_quote = quote_lines(lines, policy, card_base=ZERO)
    if method != "split":
        quote = quote_lines(lines, policy, card_base=None if method == "card" else ZERO)
        quote["expected_method"] = method
        parts = line_components(quote)
        return quote, [{"tender": method, "amount": quote["total"], "parts": parts}]
    if not isinstance(split, dict) or set(split) - set(NONCARD):
        raise ValidationError("Choose supported received tender amounts.")
    received = [
        (key, amount(split.get(key, ZERO))) for key in NONCARD if amount(split.get(key, ZERO))
    ]
    total_noncard = sum((value for _, value in received), ZERO)
    if not total_noncard or total_noncard > amount(cash_quote["total"]):
        raise ValidationError(
            "Received non-card amounts must be positive and no greater than the full non-card total."
        )
    subtotal = amount(cash_quote["subtotal"])
    taxable = amount(cash_quote["taxable_subtotal"])
    weighted_rate = Decimal(policy.tax_rate) * taxable / subtotal if subtotal else ZERO
    noncard_net = min(subtotal, money(total_noncard / (1 + weighted_rate)))
    if total_noncard == amount(cash_quote["total"]):
        noncard_net = subtotal
    # Resolve the only possible rounding edge without changing the stated tender.
    for _ in range(6):
        quote = quote_lines(lines, policy, card_base=subtotal - noncard_net)
        parts = line_components(quote)
        noncard_tax = total_noncard - noncard_net
        if ZERO <= noncard_tax <= sum((part["item_tax"] for part in parts), ZERO):
            break
        noncard_net += Decimal(".01") if noncard_tax > ZERO else Decimal("-.01")
        if not ZERO <= noncard_net <= min(subtotal, total_noncard):
            raise ValidationError("The received tender cannot be reconciled to the accepted price.")
    else:
        raise ValidationError("Review the tender rounding before collecting payment.")
    quote["expected_method"] = "card"
    net_remaining = allocate(noncard_net, [part["net"] for part in parts])
    tax_remaining = allocate(noncard_tax, [part["item_tax"] for part in parts])
    tender_taxes = allocate(noncard_tax, [value for _, value in received])
    result = []
    for (tender, value), tax in zip(received, tender_taxes):
        nets = allocate(value - tax, net_remaining)
        taxes = allocate(tax, tax_remaining)
        allocated = [
            {"net": nets[i], "fee": ZERO, "item_tax": taxes[i], "fee_tax": ZERO}
            for i in range(len(parts))
        ]
        result.append({"tender": tender, "amount": str(value), "parts": allocated})
        net_remaining = [left - used for left, used in zip(net_remaining, nets)]
        tax_remaining = [left - used for left, used in zip(tax_remaining, taxes)]
    taken = [
        {key: sum((entry["parts"][i][key] for entry in result), ZERO) for key in COMPONENTS}
        for i in range(len(parts))
    ]
    card_parts = [
        {key: part[key] - taken[i][key] for key in COMPONENTS} for i, part in enumerate(parts)
    ]
    card_value = sum((part[key] for part in card_parts for key in COMPONENTS), ZERO)
    if card_value:
        result.append({"tender": "card", "amount": str(card_value), "parts": card_parts})
    if sum((amount(entry["amount"]) for entry in result), ZERO) != amount(quote["total"]):
        raise ValidationError("The actual tender totals do not reconcile.")
    return quote, result
