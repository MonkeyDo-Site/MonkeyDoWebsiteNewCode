from .amounts import COMPONENTS, ZERO
from .invoices import effective_components


def invoice_breakdown(sale):
    effective = effective_components(sale)
    totals = {key: sum((row[key] for row in effective.values()), ZERO) for key in COMPONENTS}
    result = {
        "lines": [
            {
                "label": line.description,
                "quantity": line.quantity,
                "unit_price": f"{line.unit_price:.2f}",
                "amount": f"{effective[str(line.pk)]['net']:.2f}",
            }
            for line in sale.lines.all()
        ],
        "subtotal": f"{totals['net']:.2f}",
        "processing_fee": f"{totals['fee']:.2f}",
        "sales_tax": f"{totals['item_tax'] + totals['fee_tax']:.2f}",
        "total": f"{sum(totals.values(), ZERO):.2f}",
    }
    if sale.booking_id:
        from core.customer_credit_records import VisitMembershipConversion

        conversion = (
            VisitMembershipConversion.objects.select_related("updated_quote")
            .filter(booking_id=sale.booking_id)
            .first()
        )
        if conversion and str(sale.pk) == conversion.details.get("sale"):
            saved = conversion.updated_quote.snapshot
            if all(
                saved.get(key) == result[key]
                for key in ("subtotal", "processing_fee", "sales_tax", "total")
            ):
                result["lines"] = saved["lines"]
    return result
