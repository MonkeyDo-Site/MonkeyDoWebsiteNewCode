"""Credit covers eligible goods; a cancellation fee keeps its actual tender."""

from decimal import Decimal

from django.core.exceptions import ValidationError

from core.pricing import money, quote_lines

from .amounts import COMPONENTS, ZERO, allocate, amount

EXCLUDED = {"Partial cancellation fee", "Cancellation fee"}
MODE = "eligible-credit-v1"


def mixed(lines):
    return any(line.label in EXCLUDED and line.quantity and line.unit_price for line in lines)


def take(value, remaining, eligible=None):
    weights = [
        row[key] if key in {"net", "item_tax"} and (eligible is None or eligible[i]) else ZERO
        for i, row in enumerate(remaining)
        for key in COMPONENTS
    ]
    if value > sum(weights, ZERO):
        raise ValidationError(
            "Credit exceeds the eligible admission/socks balance after recorded Zelle."
            if eligible is not None
            else "The entered payments exceed the remaining visit amount. Adjust the amounts applied to this booking."
        )
    portions = allocate(value, weights)
    result = []
    for i, row in enumerate(remaining):
        part = {key: portions[i * len(COMPONENTS) + j] for j, key in enumerate(COMPONENTS)}
        result.append(part)
        for key in COMPONENTS:
            row[key] -= part[key]
    return result


def starting(policy, lines, prepaid=ZERO):
    from .checkout_pricing import line_components

    quote = quote_lines(lines, policy, card_base=ZERO)
    components = line_components(quote)
    bank = min(amount(prepaid), amount(quote["total"]))
    advance = take(bank, components) if bank else None
    return quote, components, advance, bank


def credit_limit(policy, lines, prepaid=ZERO):
    quote, components, _, _ = starting(policy, lines, prepaid)
    return sum(
        (
            row["net"] + row["item_tax"]
            for line, row in zip(quote["lines"], components)
            if line["label"] not in EXCLUDED
        ),
        ZERO,
    )


def components(quote):
    """Validate and reconstruct the accepted mode, never accept posted fee rows."""
    if quote.get("component_allocation") != MODE:
        raise ValidationError("Review the accepted credit allocation version.")
    lines, funding = quote["lines"], quote.get("card_funding")
    if not isinstance(funding, list) or len(funding) != len(lines):
        raise ValidationError("Card funding must match the accepted lines.")
    net = [amount(row["amount"]) for row in lines]
    card = [amount(value) for value in funding]
    base, subtotal = sum(card, ZERO), sum(net, ZERO)
    taxable = sum((value for row, value in zip(lines, net) if row["taxable"]), ZERO)
    taxable_card = sum((value for row, value in zip(lines, card) if row["taxable"]), ZERO)
    if any(value > ceiling for value, ceiling in zip(card, net)):
        raise ValidationError("Card funding exceeds its accepted line.")
    fee = money(base * Decimal(quote["rates"]["card_fee_rate"]))
    taxable_fee = money(fee * taxable_card / base) if base else ZERO
    item_tax = money(taxable * Decimal(quote["rates"]["tax_rate"]))
    tax = money((taxable + taxable_fee) * Decimal(quote["rates"]["tax_rate"]))
    expected = dict(
        subtotal=subtotal,
        taxable_subtotal=taxable,
        card_base=base,
        processing_fee=fee,
        taxable_processing_fee=taxable_fee,
        sales_tax=tax,
        total=subtotal + fee + tax,
    )
    if any(amount(quote[key]) != value for key, value in expected.items()):
        raise ValidationError("The credit/card price does not reconcile to accepted funding.")
    goods_taxes = allocate(
        item_tax, [value if row["taxable"] else ZERO for row, value in zip(lines, net)]
    )
    taxable_fees = allocate(
        taxable_fee, [value if row["taxable"] else ZERO for row, value in zip(lines, card)]
    )
    exempt_fees = allocate(
        fee - taxable_fee,
        [value if not row["taxable"] else ZERO for row, value in zip(lines, card)],
    )
    fee_taxes = allocate(tax - item_tax, taxable_fees)
    return [
        dict(
            net=net[i],
            fee=taxable_fees[i] + exempt_fees[i],
            item_tax=goods_taxes[i],
            fee_tax=fee_taxes[i],
        )
        for i in range(len(lines))
    ]


def plan(policy, lines, *, split, credit, prepaid=ZERO):
    from .checkout_pricing import NONCARD

    if not isinstance(split, dict) or set(split) - set(NONCARD):
        raise ValidationError("Choose supported received tender amounts.")
    _, remaining, advance, bank = starting(policy, lines, prepaid)
    result = []
    if bank:
        if amount(split.get("zelle", ZERO)):
            raise ValidationError(
                "Record the new Zelle receipt first, then review the remaining payment."
            )
        result.append(dict(tender="zelle", amount=str(bank), parts=advance, advance=True))
    eligible = [line.label not in EXCLUDED for line in lines]
    result.append(
        dict(tender="credit", amount=str(credit), parts=take(credit, remaining, eligible))
    )
    for kind in NONCARD:
        value = amount(split.get(kind, ZERO))
        if value:
            result.append(dict(tender=kind, amount=str(value), parts=take(value, remaining)))
    card = [row["net"] for row in remaining]
    quote = quote_lines(
        lines,
        policy,
        card_base=sum(card, ZERO),
        card_taxable_base=sum(
            (row["net"] for line, row in zip(lines, remaining) if line.taxable), ZERO
        ),
    )
    quote.update(
        expected_method="card",
        component_allocation=MODE,
        card_funding=[str(value) for value in card],
    )
    final = components(quote)
    # Goods tax remains fixed. Only the actual remaining card adds fee/tax.
    for i, row in enumerate(remaining):
        row["fee"], row["fee_tax"] = final[i]["fee"], final[i]["fee_tax"]
    card_total = sum((value for row in remaining for value in row.values()), ZERO)
    if card_total:
        result.append(dict(tender="card", amount=str(card_total), parts=remaining))
    if sum((amount(part["amount"]) for part in result), ZERO) != amount(quote["total"]):
        raise ValidationError("The credit and actual tenders do not reconcile.")
    return quote, result
