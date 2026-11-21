"""Availability, holds and payment confirmation.

The database is the final judge of double bookings (ExclusionConstraint on Booking);
these functions just make the common path fast and the race path graceful.
"""
import logging
from datetime import date, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.backends.postgresql.psycopg_any import DateRange
from django.utils import timezone

from properties.models import Unit

from .models import Booking, Payment

log = logging.getLogger(__name__)


class SoldOut(Exception):
    pass


class InvalidDates(ValueError):
    pass


def stay_range(check_in: date, check_out: date) -> DateRange:
    if check_out <= check_in:
        raise InvalidDates("Check-out must be after check-in.")
    return DateRange(check_in, check_out, "[)")


def _units_free_for(unit_type, stay: DateRange):
    busy = (
        Booking.objects.filter(unit__unit_type=unit_type, stay__overlap=stay)
        .exclude(status=Booking.Status.CANCELLED)
        .exclude(status=Booking.Status.HOLD, hold_expires_at__lt=timezone.now())
        .values("unit_id")
    )
    return Unit.objects.filter(unit_type=unit_type, is_active=True).exclude(id__in=busy).order_by("label")


def free_units(unit_type, check_in: date, check_out: date):
    return _units_free_for(unit_type, stay_range(check_in, check_out))


def release_expired_holds() -> int:
    return Booking.objects.filter(
        status=Booking.Status.HOLD, hold_expires_at__lt=timezone.now()
    ).update(status=Booking.Status.CANCELLED)


def create_hold(*, unit_type, check_in, check_out, guest, guests, quote) -> Booking:
    """Reserve one free unit of `unit_type` for HOLD minutes while the guest pays."""
    if check_in < timezone.localdate():
        raise InvalidDates("Check-in date is in the past.")
    stay = stay_range(check_in, check_out)
    now = timezone.now()

    # Expired holds still count for the constraint until cancelled — clear them first.
    Booking.objects.filter(
        unit__unit_type=unit_type, status=Booking.Status.HOLD,
        hold_expires_at__lt=now, stay__overlap=stay,
    ).update(status=Booking.Status.CANCELLED)

    for unit in _units_free_for(unit_type, stay):
        try:
            with transaction.atomic():  # savepoint: a failed insert doesn't poison the outer transaction
                return Booking.objects.create(
                    unit=unit, guest=guest, stay=stay, guests=guests,
                    status=Booking.Status.HOLD, source=Booking.Source.DIRECT,
                    total_amount=quote.total, price_breakdown=quote.as_json(),
                    hold_expires_at=now + timedelta(minutes=settings.BOOKING_HOLD_MINUTES),
                )
        except IntegrityError:
            log.info("Lost race for unit %s, trying next", unit.pk)
            continue
    raise SoldOut


def _secure_unit(booking: Booking) -> bool:
    """Turn a paid booking into CONFIRMED, re-assigning a unit if its hold lapsed."""
    if booking.status in (Booking.Status.CONFIRMED,):
        return True
    if booking.status == Booking.Status.HOLD:
        # Still a live row in the constraint → the unit is still ours, even if the timer passed.
        booking.status = Booking.Status.CONFIRMED
        booking.hold_expires_at = None
        booking.save(update_fields=["status", "hold_expires_at", "updated_at"])
        return True

    # CANCELLED: hold expired and was released. Try the same unit, then any other of the type.
    original_unit = booking.unit
    candidates = [original_unit] + list(_units_free_for(original_unit.unit_type, booking.stay).exclude(pk=original_unit.pk))
    for unit in candidates:
        try:
            with transaction.atomic():
                booking.unit = unit
                booking.status = Booking.Status.CONFIRMED
                booking.hold_expires_at = None
                booking.save(update_fields=["unit", "status", "hold_expires_at", "updated_at"])
                return True
        except IntegrityError:
            continue
    booking.unit = original_unit
    booking.status = Booking.Status.CANCELLED
    return False


def apply_successful_payment(*, reference: str, amount_subunits: int, channel: str, payload: dict):
    """Idempotent: safe to call from both the redirect callback and the webhook.

    Returns (booking, confirmed: bool).
    """
    from .notifications import alert_staff, send_confirmation  # avoid import cycle

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(reference=reference)
        booking = Booking.objects.select_for_update().get(pk=payment.booking_id)

        if payment.status == Payment.Status.SUCCESS:
            return booking, booking.status == Booking.Status.CONFIRMED

        expected = int(payment.amount * 100)
        payment.raw_payload = payload
        payment.channel = channel or ""
        if amount_subunits != expected:
            payment.status = Payment.Status.FAILED
            payment.save()
            booking.needs_attention = True
            booking.notes += f"\nAmount mismatch on {reference}: got {amount_subunits}, expected {expected}."
            booking.save(update_fields=["needs_attention", "notes", "updated_at"])
            transaction.on_commit(lambda: alert_staff(booking.pk, "Payment amount mismatch"))
            return booking, False

        payment.status = Payment.Status.SUCCESS
        payment.save()

        if _secure_unit(booking):
            transaction.on_commit(lambda: send_confirmation(booking.pk))
            return booking, True

        booking.needs_attention = True
        booking.notes += f"\nPaid ({reference}) but no unit free after hold expired — REFUND or rebook."
        booking.save(update_fields=["needs_attention", "notes", "updated_at"])
        transaction.on_commit(lambda: alert_staff(booking.pk, "Paid booking could not be placed — refund needed"))
        return booking, False
