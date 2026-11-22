import uuid
from datetime import time

from django.contrib.postgres.fields import DateRangeField
from django.db import models
from django.urls import reverse


class Branch(models.Model):
    name = models.CharField(max_length=80)                      # "Kisumu – Makasembo"
    code = models.CharField(max_length=6, unique=True)          # "MGR" — used in invoice numbers
    slug = models.SlugField(unique=True)                        # /stays/migori/
    town = models.CharField(max_length=40)
    landmark = models.CharField(max_length=160, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    maps_url = models.URLField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    intro = models.TextField(blank=True)
    hero_image = models.ImageField(upload_to="branches/", blank=True)
    check_in_time = models.TimeField(default=time(14, 0))
    check_out_time = models.TimeField(default=time(10, 0))
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "branches"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("properties:branch", args=[self.slug])

    @property
    def directions_url(self):
        return self.maps_url or f"https://maps.google.com/?q={self.latitude},{self.longitude}"


class Amenity(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "amenities"

    def __str__(self):
        return self.name


class UnitType(models.Model):
    class Bedrooms(models.IntegerChoices):
        ONE = 1, "1 Bedroom"
        TWO = 2, "2 Bedroom"
        THREE = 3, "3 Bedroom"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="unit_types")
    bedrooms = models.PositiveSmallIntegerField(choices=Bedrooms.choices)
    name = models.CharField(max_length=80)                      # "2-Bedroom Apartment"
    max_guests = models.PositiveSmallIntegerField()
    base_rate = models.DecimalField(max_digits=10, decimal_places=2, help_text="KES per night")
    min_nights = models.PositiveSmallIntegerField(default=1)
    description = models.TextField(blank=True)
    amenities = models.ManyToManyField(Amenity, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["branch", "bedrooms"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "bedrooms"], name="one_type_per_bedroom_count"),
        ]

    def __str__(self):
        return f"{self.name} · {self.branch}"


class UnitTypePhoto(models.Model):
    unit_type = models.ForeignKey(UnitType, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="units/")
    caption = models.CharField(max_length=120, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]


class Unit(models.Model):
    unit_type = models.ForeignKey(UnitType, on_delete=models.PROTECT, related_name="units")
    label = models.CharField(max_length=20)                     # "A3"
    ical_export_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["unit_type", "label"]
        constraints = [
            models.UniqueConstraint(fields=["unit_type", "label"], name="unique_unit_label"),
        ]

    def __str__(self):
        return f"{self.unit_type.branch.code}-{self.label} ({self.unit_type.get_bedrooms_display()})"

    def get_ical_export_url(self):
        return reverse("bookings:ical_export", args=[self.ical_export_token])


class CalendarFeed(models.Model):
    """An external calendar (Airbnb / Booking.com) to import for one unit."""

    class Source(models.TextChoices):
        AIRBNB = "airbnb", "Airbnb"
        BOOKING_COM = "booking_com", "Booking.com"

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="calendar_feeds")
    source = models.CharField(max_length=12, choices=Source.choices)
    url = models.URLField(max_length=500)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["unit", "source"], name="one_feed_per_source_per_unit"),
        ]

    def __str__(self):
        return f"{self.unit} ← {self.get_source_display()}"


class RateRule(models.Model):
    """Seasonal / event override. For each night the highest-priority covering rule wins."""

    unit_type = models.ForeignKey(UnitType, on_delete=models.CASCADE, related_name="rate_rules")
    name = models.CharField(max_length=60)                      # "December holidays"
    dates = DateRangeField(help_text="Nights covered: start date inclusive, end date exclusive")
    nightly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    priority = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["unit_type", "-priority"]

    def __str__(self):
        return f"{self.name} · {self.unit_type}"
