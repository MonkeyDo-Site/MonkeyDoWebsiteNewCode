"""A split visit keeps its separate, fully received membership payment explicit.

Split rows describe the visit only. The membership amount comes from its current
accepted offer, never a posted receipt amount. A card remainder is a visit charge.
"""

from django.core.exceptions import ValidationError

from .payments.amounts import ZERO, amount

MANUAL = {"cash": "Cash", "check": "Check", "gift_card": "Gift card", "zelle": "Zelle"}


def first_selection(data):
    if data.get("method") != "split" or data.get("member_first_method") != "split":
        return {}
    return dict(
        split={kind: data.get(f"member_{kind}_amount") or ZERO for kind in MANUAL},
        split_sender=data.get("member_zelle_sender", ""),
        split_received_on=data.get("member_received_on"),
    )


def first_tender(data, *, comped=False):
    if data.get("method") == "split":
        selected = data.get("member_first_method")
        if selected and (not isinstance(selected, str) or selected not in {*MANUAL, "split"}):
            raise ValidationError(
                "Choose cash, check, a verified physical gift card or a separate verified Zelle transfer for the membership payment."
            )
        # An unselected preview still needs to display the amount. Confirmation
        # rejects the placeholder if an actual membership payment is due.
        return "cash" if comped else selected or "cash"
    tender = data.get("method")
    if tender not in {"cash", "check", "card", "gift_card"}:
        raise ValidationError(
            "Choose cash, check, card or a verified physical gift card for this combined payment, or clear the membership purchase to use another arrival payment."
        )
    return tender


def split_facts(*, tender, membership_due, plan, selection, first_plan=None):
    manual = (
        {part["tender"]: amount(part["amount"]) for part in first_plan["parts"]}
        if first_plan
        else {tender: membership_due}
        if membership_due
        else {}
    )
    card = ZERO
    for part in plan:
        if part.get("advance"):
            continue
        value = amount(part["amount"])
        if part["tender"] == "card":
            card += value
        else:
            key = part["tender"]
            manual[key] = manual.get(key, ZERO) + value
    result = {
        "split_visit": True,
        "membership_first_method": selection or "",
        "manual_parts": [
            {"method": key, "label": MANUAL.get(key, key.title()), "amount": str(value)}
            for key, value in sorted(manual.items())
            if value
        ],
        "received_today": str(sum(manual.values(), ZERO)),
        "total_due_today": str(sum(manual.values(), ZERO) + card),
    }
    if card:
        result["payment_due_today"] = str(card)
    return result


def zelle_receipt(data, *, tender, due):
    if tender != "zelle" or not due:
        return {}
    from .payments.receipts import receipt_date, sender

    return {
        "membership_zelle": {
            "amount": str(due),
            "received_on": receipt_date(data.get("member_received_on")).isoformat(),
            "sender": sender(data.get("member_zelle_sender", ""), required=True),
        }
    }


def receipt_ready(data, reviewed):
    tender, facts = reviewed["offer"]["expected_method"], reviewed["facts"]
    if reviewed["offer"].get("first_payment_plan"):
        from .membership_first_split import verify

        try:
            verify(
                reviewed["offer"]["first_payment_plan"],
                verified_received=data.get("member_received"),
                gift_card_verified=data.get("gift_card_verified"),
                zelle_verified=data.get("member_zelle_verified"),
            )
        except ValidationError:
            return False
        return True
    due = facts["membership_due"] if facts.get("split_visit") else facts["received_today"]
    if facts.get("split_visit") and due != "0.00" and not data.get("member_first_method"):
        return False
    if tender == "card" or due == "0.00":
        return True
    if tender == "zelle":
        return bool(data.get("member_zelle_verified"))
    return bool(
        data.get("gift_card_verified") if tender == "gift_card" else data.get("member_received")
    )


def verify_receipt(data, reviewed, verified_received):
    tender, facts = reviewed["offer"]["expected_method"], reviewed["facts"]
    for method, field, message in (
        ("gift_card", "gift_card_verified", "Present and verify the physical gift card."),
        ("zelle", "zelle_verified", "Verify the Zelle payment in the business bank account."),
    ):
        if (
            any(
                part["tender"] == method and not part.get("advance") and amount(part["amount"])
                for part in reviewed["plan"]
            )
            and data.get(field) is not True
        ):
            raise ValidationError(message)
    due = amount(facts["membership_due"] if facts.get("split_visit") else facts["received_today"])
    if tender == "split":
        from .membership_first_split import verify

        verify(
            reviewed["offer"]["first_payment_plan"],
            verified_received=verified_received,
            gift_card_verified=data.get("gift_card_verified"),
            zelle_verified=data.get("member_zelle_verified"),
        )
        return verified_received
    if facts.get("split_visit") and due and data.get("member_first_method") not in MANUAL:
        raise ValidationError("Choose how the membership payment was received.")
    if tender == "gift_card" and due:
        if data.get("gift_card_verified") is not True:
            raise ValidationError(
                "Present and verify the physical gift card for the combined amount shown."
            )
        verified_received = True
    if tender == "zelle" and due:
        if data.get("member_zelle_verified") is not True:
            raise ValidationError(
                "Verify the separate membership Zelle transfer in the business bank account. Do not reuse Zelle already recorded for this booking."
            )
        verified_received = True
    if tender != "card" and due > ZERO and verified_received is not True:
        raise ValidationError(
            "Confirm that the membership payment was actually received."
            if facts.get("split_visit")
            else "Confirm that the combined cash or check payment was actually received."
        )
    return verified_received
