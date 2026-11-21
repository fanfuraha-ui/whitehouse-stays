import json
import logging
import secrets
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from properties.models import Unit, UnitType

from . import paystack
from .forms import GuestDetailsForm, SearchForm
from .ical import build_export
from .invoices import ensure_invoice
from .models import Booking, Guest, Payment
from .pricing import PricingError, quote
from .services import InvalidDates, SoldOut, apply_successful_payment, create_hold

log = logging.getLogger(__name__)


def checkout(request, unit_type_id):
    unit_type = get_object_or_404(UnitType.objects.select_related("branch"), pk=unit_type_id, is_active=True)
    search = SearchForm(request.GET)
    if not search.is_valid():
        messages.error(request, "Please choose your dates first.")
        return redirect(unit_type.branch.get_absolute_url())
    dates = search.cleaned_data
    if dates["guests"] > unit_type.max_guests:
        messages.error(request, f"{unit_type.name} sleeps up to {unit_type.max_guests}.")
        return redirect(f"{unit_type.branch.get_absolute_url()}?{request.GET.urlencode()}")
    try:
        price = quote(unit_type, dates["check_in"], dates["check_out"])
    except PricingError as exc:
        messages.error(request, str(exc))
        return redirect(f"{unit_type.branch.get_absolute_url()}?{request.GET.urlencode()}")

    form = GuestDetailsForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        g = form.cleaned_data
        try:
            with transaction.atomic():
                guest = Guest.objects.create(full_name=g["full_name"], phone=g["phone"],
                                             email=g["email"], address=g["address"])
                booking = create_hold(unit_type=unit_type, check_in=dates["check_in"],
                                      check_out=dates["check_out"], guest=guest,
                                      guests=dates["guests"], quote=price)
                payment = Payment.objects.create(
                    booking=booking, provider=Payment.Provider.PAYSTACK,
                    reference=f"{booking.reference}-{secrets.token_hex(3)}", amount=price.total,
                )
        except SoldOut:
            messages.error(request, "Sorry — that unit type just sold out for these dates.")
            return redirect(f"{unit_type.branch.get_absolute_url()}?{request.GET.urlencode()}")
        except InvalidDates as exc:
            messages.error(request, str(exc))
            return redirect(unit_type.branch.get_absolute_url())

        try:
            url = paystack.initialize(
                email=guest.email,
                amount_subunits=int(price.total * 100),
                reference=payment.reference,
                callback_url=request.build_absolute_uri(reverse("bookings:payment_return")),
                metadata={"booking": booking.reference, "phone": guest.phone,
                          "branch": unit_type.branch.code, "unit_type": unit_type.name},
            )
        except (paystack.PaystackError, Exception) as exc:  # network errors included
            log.exception("Paystack init failed for %s", booking.reference)
            booking.status = Booking.Status.CANCELLED
            booking.save(update_fields=["status", "updated_at"])
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status", "updated_at"])
            messages.error(request, "We couldn't start the payment. Please try again or WhatsApp us.")
            return redirect(request.get_full_path())
        return redirect(url)

    return render(request, "bookings/checkout.html", {
        "unit_type": unit_type, "branch": unit_type.branch, "dates": dates, "quote": price, "form": form,
    })


def payment_return(request):
    reference = request.GET.get("reference") or request.GET.get("trxref")
    payment = get_object_or_404(Payment.objects.select_related("booking"), reference=reference)
    try:
        data = paystack.verify(reference)
    except Exception:
        log.exception("Verify failed for %s", reference)
        return render(request, "bookings/payment_pending.html", {"booking": payment.booking})

    if data.get("status") == "success":
        booking, confirmed = apply_successful_payment(
            reference=reference, amount_subunits=int(data["amount"]),
            channel=data.get("channel", ""), payload=data,
        )
        return redirect("bookings:confirmation", reference=booking.reference)

    if data.get("status") in ("failed", "abandoned", "reversed"):
        payment.status = Payment.Status.FAILED
        payment.raw_payload = data
        payment.save(update_fields=["status", "raw_payload", "updated_at"])
        Booking.objects.filter(pk=payment.booking_id, status=Booking.Status.HOLD).update(
            status=Booking.Status.CANCELLED)  # free the unit for the retry
        return render(request, "bookings/payment_failed.html", {"booking": payment.booking})

    return render(request, "bookings/payment_pending.html", {"booking": payment.booking})


@csrf_exempt
@require_POST
def paystack_webhook(request):
    if not paystack.valid_signature(request.body, request.headers.get("x-paystack-signature", "")):
        return HttpResponseBadRequest("bad signature")
    try:
        event = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest("bad json")

    if event.get("event") == "charge.success":
        data = event.get("data", {})
        reference = data.get("reference", "")
        if Payment.objects.filter(reference=reference).exists():
            apply_successful_payment(reference=reference, amount_subunits=int(data.get("amount", 0)),
                                     channel=data.get("channel", ""), payload=data)
        else:
            log.warning("Webhook for unknown reference %s", reference)
    return HttpResponse(status=200)  # always 200 for valid signatures so Paystack stops retrying


def confirmation(request, reference):
    booking = get_object_or_404(
        Booking.objects.select_related("unit__unit_type__branch", "guest"), reference=reference,
        source=Booking.Source.DIRECT,
    )
    return render(request, "bookings/confirmation.html", {"booking": booking})


def ical_export(request, token):
    unit = get_object_or_404(Unit, ical_export_token=token)
    response = HttpResponse(build_export(unit), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'inline; filename="whitehouse-{unit.pk}.ics"'
    return response


@staff_member_required
def invoice_pdf(request, reference):
    booking = get_object_or_404(Booking, reference=reference)
    if booking.status != Booking.Status.CONFIRMED:
        raise Http404("Invoices are issued for confirmed bookings only")
    invoice = ensure_invoice(booking)
    return FileResponse(invoice.pdf.open("rb"), content_type="application/pdf",
                        filename=f"{invoice.number}.pdf")
