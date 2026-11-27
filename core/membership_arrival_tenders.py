"""A split visit keeps its separate, fully received membership payment explicit.

Split rows describe the visit only. The membership amount comes from its current
accepted offer, never a posted receipt amount. A card remainder is a visit charge.
"""

from django.core.exceptions import ValidationError

from .payments.amounts import ZERO, amount

MANUAL = {"cash": "Cash", "check": "Check", "gift_card": "Gift card"}


def first_tender(data, *, comped=False):
    if data.get("method") == "split":
        selected = data.get("member_first_method")
        if selected and (not isinstance(selected, str) or selected not in MANUAL):
            raise ValidationError(
                "Choose cash, check or a verified physical gift card for the membership payment."
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


def split_facts(*, tender, membership_due, plan, selection):
    manual = {tender: membership_due} if membership_due else {}
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


def receipt_ready(data, reviewed):
    tender, facts = reviewed["offer"]["expected_method"], reviewed["facts"]
    due = facts["membership_due"] if facts.get("split_visit") else facts["received_today"]
    if facts.get("split_visit") and due != "0.00" and not data.get("member_first_method"):
        return False
    if tender == "card" or due == "0.00":
        return True
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
    if facts.get("split_visit") and due and data.get("member_first_method") not in MANUAL:
        raise ValidationError("Choose how the membership payment was received.")
    if tender == "gift_card" and due:
        if data.get("gift_card_verified") is not True:
            raise ValidationError(
                "Present and verify the physical gift card for the combined amount shown."
            )
        verified_received = True
    if tender != "card" and due > ZERO and verified_received is not True:
        raise ValidationError(
            "Confirm that the membership payment was actually received."
            if facts.get("split_visit")
            else "Confirm that the combined cash or check payment was actually received."
        )
    return verified_received
