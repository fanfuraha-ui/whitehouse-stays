"""Branded invoice PDF matching the paper Whitehouse invoice (navy/gold)."""
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Booking, Invoice


def invoice_number(booking: Booking) -> str:
    return f"WH-{booking.branch.code}-{booking.created_at:%Y}-{booking.pk:05d}"


def invoice_lines(booking: Booking):
    """Rows for the No./Description/Qty/Unit Price/Amount table."""
    unit_type = booking.unit_type
    lines = booking.price_breakdown or [
        {"label": "Accommodation", "nights": booking.nights, "rate": str(booking.total_amount / max(booking.nights, 1)),
         "amount": str(booking.total_amount)}
    ]
    rows = []
    for i, line in enumerate(lines, start=1):
        rows.append({
            "no": i,
            "description": f"{unit_type.name}, {booking.branch.name} — {line['label']} "
                           f"({booking.check_in:%d %b} – {booking.check_out:%d %b %Y})",
            "qty": line["nights"],
            "unit_price": Decimal(line["rate"]),
            "amount": Decimal(line["amount"]),
        })
    return rows


@transaction.atomic
def ensure_invoice(booking: Booking) -> Invoice:
    invoice = Invoice.objects.select_for_update().filter(booking=booking).first()
    if invoice is None:
        rows = invoice_lines(booking)
        subtotal = sum((r["amount"] for r in rows), Decimal("0"))
        tax = (subtotal * settings.TAX_RATE).quantize(Decimal("0.01"))
        invoice = Invoice.objects.create(
            booking=booking,
            number=invoice_number(booking),
            issued_on=timezone.localdate(),
            due_on=booking.check_in,
            subtotal=subtotal,
            tax=tax,
            total=subtotal + tax,
        )
    if not invoice.pdf:
        invoice.pdf.save(f"{invoice.number}.pdf", ContentFile(render_pdf(invoice)), save=True)
    return invoice


def render_pdf(invoice: Invoice) -> bytes:
    from weasyprint import HTML  # heavy import; only load when needed

    booking = invoice.booking
    html = render_to_string("invoices/invoice.html", {
        "invoice": invoice,
        "booking": booking,
        "guest": booking.guest,
        "rows": invoice_lines(booking),
        "BRAND": settings.BRAND,
        "amount_paid": booking.amount_paid,
    })
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
