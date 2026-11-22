import logging

from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from django.template.loader import render_to_string

from .models import Booking

log = logging.getLogger(__name__)


def send_confirmation(booking_pk: int):
    from .invoices import ensure_invoice

    booking = Booking.objects.select_related("guest", "unit__unit_type__branch").get(pk=booking_pk)
    if not booking.guest or not booking.guest.email:
        return
    try:
        invoice = ensure_invoice(booking)
    except Exception:  # never lose the confirmation email because the PDF failed
        log.exception("Invoice generation failed for %s", booking.reference)
        invoice = None

    body = render_to_string("bookings/email_confirmation.txt", {"booking": booking, "BRAND": settings.BRAND,
                                                                "SITE_URL": settings.SITE_URL})
    message = EmailMessage(
        subject=f"Booking confirmed — {booking.reference} · {settings.BRAND['name']}",
        body=body,
        to=[booking.guest.email],
        bcc=settings.STAFF_ALERT_EMAILS,
    )
    if invoice and invoice.pdf:
        invoice.pdf.open("rb")
        message.attach(f"{invoice.number}.pdf", invoice.pdf.read(), "application/pdf")
        invoice.pdf.close()
    try:
        message.send()
    except Exception:
        log.exception("Confirmation email failed for %s", booking.reference)


def alert_staff(booking_pk: int, subject: str):
    booking = Booking.objects.select_related("guest", "unit__unit_type__branch").get(pk=booking_pk)
    log.warning("STAFF ALERT %s: %s", booking.reference, subject)
    if not settings.STAFF_ALERT_EMAILS:
        return
    send_mail(
        subject=f"[Whitehouse] {subject} — {booking.reference}",
        message=(
            f"Booking {booking.reference}\nBranch: {booking.branch}\nUnit: {booking.unit}\n"
            f"Dates: {booking.check_in} → {booking.check_out}\nGuest: {booking.guest}\n\n"
            f"Notes:\n{booking.notes}\n\nOpen: {settings.SITE_URL}/admin/bookings/booking/{booking.pk}/change/"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=settings.STAFF_ALERT_EMAILS,
        fail_silently=True,
    )
