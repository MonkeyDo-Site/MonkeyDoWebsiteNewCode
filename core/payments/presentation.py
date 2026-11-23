from .amounts import COMPONENTS, ZERO
from .invoices import effective_components


def invoice_breakdown(sale):
    effective = effective_components(sale)
    totals = {key: sum((row[key] for row in effective.values()), ZERO) for key in COMPONENTS}
    return {
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
