"""iCal import (Airbnb / Booking.com → BLOCKED bookings) and export (our bookings → them).

Analogy: iCal is a newspaper, not a phone call — each side re-reads the other's
calendar on a schedule, so there is always a short window where they disagree.
"""
import logging
from datetime import date, datetime, timedelta

import icalendar
import requests
from django.db import IntegrityError, transaction
from django.db.backends.postgresql.psycopg_any import DateRange
from django.utils import timezone

from properties.models import CalendarFeed

from .models import Booking

log = logging.getLogger(__name__)


def _as_date(value) -> date:
    return value.date() if isinstance(value, datetime) else value


def sync_feed(feed: CalendarFeed) -> dict:
    stats = {"created": 0, "updated": 0, "cancelled": 0, "conflicts": 0}
    today = timezone.localdate()
    try:
        resp = requests.get(feed.url, timeout=30, headers={"User-Agent": "WhitehouseAirbnb/1.0"})
        resp.raise_for_status()
        calendar = icalendar.Calendar.from_ical(resp.content)
    except Exception as exc:
        feed.last_error = f"{timezone.now():%Y-%m-%d %H:%M} {exc}"
        feed.save(update_fields=["last_error"])
        log.warning("iCal fetch failed for %s: %s", feed, exc)
        return stats

    seen_uids = set()
    for event in calendar.walk("VEVENT"):
        uid = str(event.get("UID", "")).strip()
        if not uid or "DTSTART" not in event:
            continue
        start = _as_date(event.decoded("DTSTART"))
        end = _as_date(event.decoded("DTEND")) if "DTEND" in event else start + timedelta(days=1)
        if end <= today or end <= start:
            continue
        seen_uids.add(uid)
        stay = DateRange(start, end, "[)")
        existing = (
            Booking.objects.filter(unit=feed.unit, external_uid=uid, source=feed.source)
            .exclude(status=Booking.Status.CANCELLED).first()
        )
        try:
            with transaction.atomic():
                if existing:
                    if (existing.stay.lower, existing.stay.upper) != (start, end):
                        existing.stay = stay
                        existing.save(update_fields=["stay", "updated_at"])
                        stats["updated"] += 1
                else:
                    Booking.objects.create(
                        unit=feed.unit, stay=stay, status=Booking.Status.BLOCKED,
                        source=feed.source, external_uid=uid,
                        notes=str(event.get("SUMMARY", ""))[:200],
                    )
                    stats["created"] += 1
        except IntegrityError:
            # A real double booking already exists across platforms — humans must resolve it.
            stats["conflicts"] += 1
            log.error("iCal CONFLICT on %s %s–%s (uid %s)", feed.unit, start, end, uid)
            Booking.objects.filter(unit=feed.unit, stay__overlap=stay).exclude(
                status=Booking.Status.CANCELLED
            ).update(needs_attention=True)

    # Events removed on the other platform → free the dates here.
    stale = (
        Booking.objects.filter(unit=feed.unit, source=feed.source, status=Booking.Status.BLOCKED)
        .exclude(external_uid="").exclude(external_uid__in=seen_uids)
        .filter(stay__endswith__gt=today)  # only future/ongoing blocks
    )
    stats["cancelled"] = stale.update(status=Booking.Status.CANCELLED)

    feed.last_synced_at = timezone.now()
    feed.last_error = ""
    feed.save(update_fields=["last_synced_at", "last_error"])
    return stats


def build_export(unit) -> bytes:
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Whitehouse Airbnb//Direct Bookings//EN")
    cal.add("version", "2.0")
    now = timezone.now()
    bookings = (
        Booking.objects.filter(unit=unit, stay__endswith__gt=timezone.localdate() - timedelta(days=30))
        .exclude(status=Booking.Status.CANCELLED)
        .exclude(status=Booking.Status.HOLD, hold_expires_at__lt=now)
    )
    for booking in bookings:
        event = icalendar.Event()
        event.add("uid", f"{booking.reference}@whitehouse")
        event.add("dtstamp", now)
        event.add("dtstart", booking.stay.lower)
        event.add("dtend", booking.stay.upper)
        event.add("summary", "Reserved")  # never leak guest names to other platforms
        cal.add_component(event)
    return cal.to_ical()
