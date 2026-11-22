from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from properties.models import Amenity, Branch, UnitType

BRANCHES = [
    {
        "code": "MGR", "slug": "migori", "name": "Migori", "town": "Migori",
        "landmark": "Behind Machage Hospital, next to Joybeck Apartment",
        "latitude": Decimal("-1.088933"), "longitude": Decimal("34.462582"),
        "maps_url": "https://maps.google.com/?q=-1.088933,34.462582", "sort_order": 1,
    },
    {
        "code": "KSM1", "slug": "kisumu-makasembo", "name": "Kisumu – Makasembo", "town": "Kisumu",
        "landmark": "Makasembo housing by Lapfund",
        # Approximate; confirm exact coordinates in admin.
        "latitude": Decimal("-0.102908"), "longitude": Decimal("34.770588"),
        "maps_url": "https://maps.app.goo.gl/STuGwUYXdtNdMMXo9", "sort_order": 2,
    },
    {
        "code": "KSM2", "slug": "kisumu", "name": "Kisumu", "town": "Kisumu",
        "landmark": "",  # TODO: branch landmark
        "latitude": Decimal("-0.102908"), "longitude": Decimal("34.770588"),
        "maps_url": "https://maps.google.com/?q=-0.102908,34.770588", "sort_order": 3,
    },
]

UNIT_TYPES = [
    # bedrooms, name, max_guests, placeholder rate (KES) — replace in admin
    (1, "1-Bedroom Apartment", 2, Decimal("3500")),
    (2, "2-Bedroom Apartment", 4, Decimal("5500")),
    (3, "3-Bedroom Apartment", 6, Decimal("7500")),
]

AMENITIES = ["Wi-Fi", "Secure parking", "Hot shower", "Smart TV", "Fully equipped kitchen",
             "24/7 security", "Housekeeping", "Backup power"]


class Command(BaseCommand):
    help = "Create the three Whitehouse branches with 1/2/3-bedroom unit types (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        amenities = [Amenity.objects.get_or_create(name=n)[0] for n in AMENITIES]
        for data in BRANCHES:
            branch, created = Branch.objects.update_or_create(
                code=data["code"], defaults={**data, "phone": "0710110524"}
            )
            self.stdout.write(f"{'Created' if created else 'Updated'} branch {branch}")
            for bedrooms, name, max_guests, rate in UNIT_TYPES:
                unit_type, _ = UnitType.objects.get_or_create(
                    branch=branch, bedrooms=bedrooms,
                    defaults={"name": name, "max_guests": max_guests, "base_rate": rate},
                )
                unit_type.amenities.add(*amenities)
        self.stdout.write(self.style.SUCCESS(
            "Done. Add units, photos and real rates in /admin/ before going live."
        ))
