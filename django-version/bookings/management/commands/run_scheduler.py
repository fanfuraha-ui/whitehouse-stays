"""Long-running scheduler for the `scheduler` container.

- every minute: release expired payment holds
- every 15 minutes: import Airbnb / Booking.com calendars
"""
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from bookings.ical import sync_feed
from bookings.services import release_expired_holds
from properties.models import CalendarFeed

ICAL_EVERY_SECONDS = 15 * 60


class Command(BaseCommand):
    help = "Run background jobs forever (holds every minute, iCal every 15 minutes)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run each job once and exit")

    def handle(self, *args, **options):
        last_ical = 0.0
        while True:
            close_old_connections()
            try:
                released = release_expired_holds()
                if released:
                    self.stdout.write(f"Released {released} expired hold(s)")
                if options["once"] or time.monotonic() - last_ical >= ICAL_EVERY_SECONDS:
                    for feed in CalendarFeed.objects.select_related("unit"):
                        stats = sync_feed(feed)
                        self.stdout.write(f"iCal {feed}: {stats}")
                    last_ical = time.monotonic()
            except Exception as exc:  # keep the loop alive; errors are logged
                self.stderr.write(f"Scheduler error: {exc!r}")
            if options["once"]:
                return
            time.sleep(60)
