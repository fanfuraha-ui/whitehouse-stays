import secrets

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.db import models
from django.db.models import Q

REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I confusion


def new_reference():
    return "WH-" + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(6))


class Guest(models.Model):
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=15, db_index=True, help_text="2547XXXXXXXX")
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


class Booking(models.Model):
    class Status(models.TextChoices):
        HOLD = "hold", "Hold (awaiting payment)"
        CONFIRMED = "confirmed", "Confirmed"
        BLOCKED = "blocked", "Blocked (maintenance / other platform)"
        CANCELLED = "cancelled", "Cancelled"

    class Source(models.TextChoices):
        DIRECT = "direct", "Website"
        WALK_IN = "walk_in", "Walk-in"
        PHONE = "phone", "Phone / WhatsApp"
        AIRBNB = "airbnb", "Airbnb"
        BOOKING_COM = "booking_com", "Booking.com"
        OWNER = "owner", "Owner / maintenance"

    reference = models.CharField(max_length=16, unique=True, blank=True)
    unit = models.ForeignKey("properties.Unit", on_delete=models.PROTECT, related_name="bookings")
    guest = models.ForeignKey(Guest, null=True, blank=True, on_delete=models.PROTECT, related_name="bookings")
    stay = DateRangeField(help_text="Check-in date to check-out date (check-out day is free for the next guest)")
    guests = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONFIRMED)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.WALK_IN)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_breakdown = models.JSONField(default=list, blank=True)   # snapshot at booking time
    hold_expires_at = models.DateTimeField(null=True, blank=True)
    external_uid = models.CharField(max_length=255, blank=True, db_index=True)  # iCal UID
    needs_attention = models.BooleanField(default=False, help_text="Staff must review (payment/sync issue)")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            ExclusionConstraint(
                name="no_overlapping_stays",
                expressions=[("unit", RangeOperators.EQUAL), ("stay", RangeOperators.OVERLAPS)],
                condition=~Q(status="cancelled"),
                violation_error_message="This unit is already booked for some of these dates.",
            ),
        ]

    def __str__(self):
        return f"{self.reference} · {self.unit}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = new_reference()
        super().save(*args, **kwargs)

    @property
    def unit_type(self):
        return self.unit.unit_type

    @property
    def branch(self):
        return self.unit.unit_type.branch

    @property
    def check_in(self):
        return self.stay.lower

    @property
    def check_out(self):
        return self.stay.upper

    @property
    def nights(self):
        return (self.stay.upper - self.stay.lower).days

    @property
    def amount_paid(self):
        total = self.payments.filter(status=Payment.Status.SUCCESS).aggregate(s=models.Sum("amount"))["s"]
        return total or 0

    @property
    def balance(self):
        return self.total_amount - self.amount_paid


class Payment(models.Model):
    class Provider(models.TextChoices):
        PAYSTACK = "paystack", "Paystack (M-Pesa / card)"
        CASH = "cash", "Cash at desk"
        MPESA_TILL = "mpesa_till", "M-Pesa at desk"

    class Status(models.TextChoices):
        PENDING = "pending"
        SUCCESS = "success"
        FAILED = "failed"
        REFUNDED = "refunded"

    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=12, choices=Provider.choices)
    reference = models.CharField(max_length=100, unique=True, help_text="Paystack ref or M-Pesa code")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    channel = models.CharField(max_length=30, blank=True)          # mobile_money / card
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} · KES {self.amount} · {self.status}"


class Invoice(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.PROTECT, related_name="invoice")
    number = models.CharField(max_length=24, unique=True)          # WH-MGR-2026-00042
    issued_on = models.DateField()
    due_on = models.DateField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    pdf = models.FileField(upload_to="invoices/%Y/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.number
