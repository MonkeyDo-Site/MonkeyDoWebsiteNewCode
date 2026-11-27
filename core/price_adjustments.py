"""Read-only explanation of a current quote against the first immutable booking quote."""

from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0.00")
SOCKS = "Grip socks — pick up upon arrival"
FEE_LABELS = {"Partial cancellation fee", "Cancellation fee"}
OWNER = "Owner-priced admissions"
MEMBER_CHILDREN = {
    "Child admissions — Unlimited membership",
    "Child admissions — Subscription free visits",
    "Child admissions — Subscription additional visits",
    "Supervised child admissions — Subscription discount",
}
CHILDREN = MEMBER_CHILDREN | {"Child admissions", "Supervised child admissions"}
TYPES = {
    "Child admissions — Unlimited membership": ("children", "admissions"),
    "Child admissions — Subscription free visits": ("children", "admissions"),
    "Child admissions — Subscription additional visits": ("children", "admissions"),
    "Supervised child admissions — Subscription discount": ("children", "admissions"),
    "Child admissions": ("children", "admissions"),
    "Supervised child admissions": ("children", "admissions"),
    "Required baby admission": ("baby_minimum", "admissions"),
    "Required adult admission": ("adult_minimum", "admissions"),
    "Additional adults": ("extra_adults", "adult admissions"),
    SOCKS: ("socks", "socks"),
}


def named_types(values):
    values = list(dict.fromkeys(values))
    return values[0] if len(values) == 1 else ", ".join(values[:-1]) + " and " + values[-1]


def compare_prices(original, current):
    """Explain exact saved cents; never infer a payment, refund or cancellation fee."""
    if not all(
        key in original and key in current
        for key in ("lines", "subtotal", "processing_fee", "sales_tax", "total")
    ):
        return None
    rows = []

    def row(label, delta):
        if delta:
            rows.append(
                {
                    "label": label,
                    "delta": delta,
                    "amount": abs(delta),
                    "sign": "+" if delta > 0 else "−",
                }
            )

    old_lines = original["lines"]
    new_lines = current["lines"]
    owner_priced = any(line["label"] == OWNER for line in old_lines + new_lines)
    complimentary = bool(original.get("owner_comped") or current.get("owner_comped"))
    skipped = set(FEE_LABELS)
    if owner_priced or complimentary:
        skipped.update(
            line["label"]
            for line in old_lines + new_lines
            if complimentary or line["label"] != SOCKS
        )

        def owner_net(lines):
            return sum(
                (
                    Decimal(line["amount"])
                    for line in lines
                    if line["label"] not in FEE_LABELS and (complimentary or line["label"] != SOCKS)
                ),
                ZERO,
            )

        row(
            "Owner complimentary price adjustment" if complimentary else "Owner pricing adjustment",
            owner_net(new_lines) - owner_net(old_lines),
        )

    def items(lines):
        result = {}
        for line in lines:
            if line["label"] in skipped:
                continue
            key, label = TYPES.get(line["label"], (line["label"], "items"))
            entry = result.setdefault(key, {"quantity": 0, "amount": ZERO, "type": label})
            entry["quantity"] += line["quantity"]
            entry["amount"] += Decimal(line["amount"])
        return result

    added = ZERO
    removed = ZERO
    add_names = []
    remove_names = []
    repricing = ZERO
    benefit_delta = ZERO
    if (
        not owner_priced
        and not complimentary
        and any(line["label"] in MEMBER_CHILDREN for line in old_lines + new_lines)
    ):
        # Preserve the marginal paid admissions when free and paid children
        # coexist. Averaging $15 over two free and one paid child would falsely
        # describe a removed $15 admission as $5 plus a $10 price change.
        def cost(lines, units):
            remaining = units
            result = ZERO
            baskets = sorted(
                (
                    (Decimal(line["amount"]) / line["quantity"], line["quantity"])
                    for line in lines
                    if line["quantity"]
                ),
                reverse=True,
            )
            for unit, quantity in baskets:
                taken = min(remaining, quantity)
                result += unit * taken
                remaining -= taken
            return result.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)

        categories = [(CHILDREN, "admissions", None)]
        old_attendees, new_attendees = (
            original.get("membership_attendees", {}),
            current.get("membership_attendees", {}),
        )
        if "adults" in old_attendees and "adults" in new_attendees:
            categories.append(({"Additional adults"}, "adult admissions", "adults"))
        for labels, name, attendee in categories:
            before = [line for line in old_lines if line["label"] in labels]
            after = [line for line in new_lines if line["label"] in labels]
            old_qty = (
                old_attendees[attendee] if attendee else sum(line["quantity"] for line in before)
            )
            new_qty = (
                new_attendees[attendee] if attendee else sum(line["quantity"] for line in after)
            )
            plus, minus = (
                cost(after, max(0, new_qty - old_qty)),
                cost(before, max(0, old_qty - new_qty)),
            )
            added += plus
            removed += minus
            if plus:
                add_names.append(name)
            if minus:
                remove_names.append(name)
            benefit_delta += (
                sum((Decimal(line["amount"]) for line in after), ZERO)
                - sum((Decimal(line["amount"]) for line in before), ZERO)
                - plus
                + minus
            )
            skipped.update(labels)
    old = items(old_lines)
    new = items(new_lines)
    for key in sorted(old.keys() | new.keys()):
        before = (
            old[key] if key in old else {"quantity": 0, "amount": ZERO, "type": new[key]["type"]}
        )
        after = new.get(key, {"quantity": 0, "amount": ZERO, "type": before["type"]})
        old_qty = before["quantity"]
        new_qty = after["quantity"]
        # Aggregate totals can include a later itemized correction. Quantities
        # explain the count change; the residual is explicitly price adjustment.
        if new_qty > old_qty and new_qty:
            value = (after["amount"] * (new_qty - old_qty) / new_qty).quantize(
                Decimal(".01"), rounding=ROUND_HALF_UP
            )
            added += value
            if value:
                add_names.append(after["type"])
            repricing += after["amount"] - before["amount"] - value
        elif old_qty > new_qty and old_qty:
            value = (before["amount"] * (old_qty - new_qty) / old_qty).quantize(
                Decimal(".01"), rounding=ROUND_HALF_UP
            )
            removed += value
            if value:
                remove_names.append(before["type"])
            repricing += after["amount"] - before["amount"] + value
        else:
            repricing += after["amount"] - before["amount"]
    row("Plus additional " + named_types(add_names) if add_names else "", added)
    row("Minus cancelled " + named_types(remove_names) if remove_names else "", -removed)
    row("Admission/item price adjustment", repricing)
    row("Membership benefit adjustment", benefit_delta)
    old_fees = sum(
        (Decimal(line["amount"]) for line in old_lines if line["label"] in FEE_LABELS), ZERO
    )
    new_fees = sum(
        (Decimal(line["amount"]) for line in new_lines if line["label"] in FEE_LABELS), ZERO
    )
    row(
        "Credit-card processing-fee adjustment",
        Decimal(current["processing_fee"]) - Decimal(original["processing_fee"]),
    )
    row("Sales-tax adjustment", Decimal(current["sales_tax"]) - Decimal(original["sales_tax"]))
    row(
        "Plus cancellation fee (no sales tax)"
        if new_fees > old_fees
        else "Cancellation fee adjustment (no sales tax)",
        new_fees - old_fees,
    )
    # Preserve exact reconciliation for historical/specially adjusted line sets.
    difference = Decimal(current["total"]) - Decimal(original["total"])
    row("Other pricing adjustment", difference - sum((r["delta"] for r in rows), ZERO))
    if not rows:
        return None
    return {
        "original_total": Decimal(original["total"]),
        "rows": rows,
        "total": Decimal(current["total"]),
    }


def booking_price_adjustment(booking, current):
    first = booking.quotes.order_by("revision", "pk").first()
    if not first:
        return None
    if Decimal(current.get("total", "0")) == ZERO:
        from .payments.models import BookingChargeState

        if BookingChargeState.objects.filter(booking=booking, comped=True).exists():
            current = dict(current, owner_comped=True)
    return compare_prices(first.snapshot, current)
