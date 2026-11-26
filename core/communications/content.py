"""Accepted ordinary-booking email wording with actual estimate/delivery facts."""

from decimal import Decimal

from django.conf import settings
from django.urls import reverse

from core.date_display import display_date, display_time_range
from core.payments.policy import CANCELLATION_SCOPE


def plural(count, singular, multiple):
    return f"{count} {singular if count == 1 else multiple}"


def session_subject(booking, title="Your MonkeyDo adventure is booked!"):
    day = display_date(booking.session.starts_at, "l, F j")
    times = display_time_range(booking.session.starts_at, booking.session.ends_at)
    return f"{title} - {day}, {times}"


def zelle_instructions():
    return (
        "Please send payment by Zelle at any time to monkeydoplay@gmail.com. "
        "If the Zelle isn’t received before the visit and cannot be taken care of upon arrival, "
        "your backup card will be charged."
    )


def booking_confirmation(booking, *, waiver_url=None, waiver_type="single", comped=False):
    from core.payments.models import BookingChargeState

    comped = comped or BookingChargeState.objects.filter(booking=booking, comped=True).exists()
    quote = dict(booking.quotes.first().snapshot)
    checkout = booking.checkouts.select_related("sale").order_by("-created_at").first()
    actual = None
    if checkout and checkout.sale:
        from core.payments.amounts import COMPONENTS, ZERO
        from core.payments.invoices import effective_components, received

        values = effective_components(checkout.sale).values()
        totals = {key: sum((row[key] for row in values), ZERO) for key in COMPONENTS}
        quote.update(
            subtotal=str(totals["net"]),
            processing_fee=str(totals["fee"]),
            sales_tax=str(totals["item_tax"] + totals["fee_tax"]),
            total=str(sum(totals.values(), ZERO)),
        )
        actual = received(checkout.sale)
        corrected = checkout.sale.operations.exclude(kind="receipt").exists()
    lines = [
        f"Dear Family {booking.customer.last_name},",
        "",
        "You're all set for your MonkeyDo adventure!",
        "",
        "We look forward to seeing you "
        + display_date(booking.session.starts_at, "l, F j, Y")
        + " at "
        + display_time_range(booking.session.starts_at, booking.session.ends_at)
        + ".",
        " · ".join(
            [
                plural(booking.adults, "adult", "adults"),
                plural(booking.children, "child", "children"),
                plural(booking.babies, "baby", "babies"),
            ]
        ),
        "",
        "Your booking is complimentary. No payment or card is required." if comped else "",
    ]
    for item in quote["lines"]:
        lines.append(
            f"{item['label']}: {plural(item['quantity'], 'pair of socks', 'pairs of socks') if item['label'].startswith('Grip socks') else item['quantity']} × ${item['unit_price']} = ${item['amount']}"
        )
    lines.append(f"Subtotal: ${quote['subtotal']}")
    if Decimal(quote["processing_fee"]):
        lines.append(f"Credit-card processing fee: ${quote['processing_fee']}")
    lines.append(f"Sales tax: ${quote['sales_tax']}")
    if actual is None and not comped:
        lines.extend(
            [
                f"Your total is ${quote['total']}.",
                (
                    "You selected to pay via credit card. Your card will be charged upon arrival."
                    if booking.expected_method == "card"
                    else f"You selected to pay via {booking.get_expected_method_display()}, which is due upon arrival."
                    if booking.expected_method in {"cash", "check"}
                    else ""
                ),
            ]
        )
    elif actual is not None:
        lines.extend(
            [
                f"Actual payment received, net of recorded reversals: ${actual:.2f}",
                (
                    "A recorded correction requires owner review; this message does not request another payment."
                    if corrected
                    else f"Remaining amount: ${max(Decimal('0'), Decimal(quote['total']) - actual):.2f}"
                ),
                "No admission payment was collected online.",
            ]
        )
    if booking.expected_method == "zelle" and not comped:
        lines.extend(
            [
                "",
                ("You selected to pay via Zelle. " + zelle_instructions())
                if actual is None
                else "You selected Zelle as your form of payment. Please Zelle payment to monkeydoplay@gmail.com only for any verified remaining balance.",
            ]
        )
    if booking.expected_method == "gift_card" and not comped:
        lines.extend(["", "Gift card must be presented upon arrival."])
    if not booking.socks:
        lines.append("Please remember to bring along your grip socks.")
    if waiver_url:
        lines.append("")
        if waiver_type == "multiple":
            lines.append(
                "Please see the PDF waiver file attached. Please ensure a parent of each minor who will be coming signs the waiver. Please bring along the signed waivers as they are required. Alternatively, you can send the link below to each parent to sign electronically."
            )
        elif waiver_type == "online_shared":
            lines.append(
                "Please see below the waiver link that you requested to send to parents of other minors included in your booking. Alternatively, we've attached a PDF waiver file that you can print, have them sign and bring along when you come."
            )
        else:
            lines.append(
                "We prefer that you complete your waiver before your visit using this secure link. If you don't get to it before your appointment, you'll be able to sign it when you arrive."
            )
        lines.append(waiver_url)
    lines.extend(
        [
            "",
            "Swing your way over to: 56 Budleman Way, Lakewood, NJ 08701",
            "Please use the basement entrance. Parking is in the driveway or cul-de-sac.",
            "",
            "In the event that you must cancel, please call or text us at 848-238-5147."
            + ("" if comped else " Cancellation fees will apply."),
        ]
    )
    if booking.source == "staff" and not comped:
        from core.payments.policy import displayed_cancellation

        lines.append(
            displayed_cancellation({"staff_booking": booking.pk})[0] + " " + CANCELLATION_SCOPE
        )
    lines.extend(["", "Get ready to go bananas,", "The MonkeyDo team"])
    body = "\n".join(lines)
    while "\n\n\n" in body:
        body = body.replace("\n\n\n", "\n\n")
    return body


def waiver_completed(signature, booking):
    return "\n".join(
        [
            f"Dear Family {booking.customer.last_name},",
            "",
            "A waiver has been completed for your MonkeyDo booking.",
            "Appointment: " + display_date(booking.session.starts_at, "l, F j, Y g:i A"),
            "Signing adult: " + signature.signer_name,
            "Minors covered: " + (", ".join(signature.minors) or "Signing for self only"),
            "",
            "The MonkeyDo team",
        ]
    )


def owner_payment_issue(operation):
    booking = operation.sale.booking
    appointment = (
        display_date(booking.session.starts_at, "l, F j, Y g:i A")
        if booking
        else "Not tied to a visit"
    )
    return "\n".join(
        [
            "A MonkeyDo sandbox payment needs review.",
            "Family: " + operation.sale.customer.last_name,
            "Phone: " + operation.sale.customer.phone,
            "Appointment: " + appointment,
            f"Amount: ${operation.amount}",
            "Status: " + operation.get_state_display(),
            "Review: "
            + settings.BOOKING_STAGING_ORIGIN
            + reverse("payment_detail", args=[operation.pk]),
            "No automatic payment retry will be made.",
        ]
    )
