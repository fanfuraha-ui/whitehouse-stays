"""Nightly pricing: for each night, the highest-priority RateRule covering it, else base_rate."""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.backends.postgresql.psycopg_any import DateRange

MAX_NIGHTS = 60


class PricingError(ValueError):
    pass


@dataclass
class Quote:
    check_in: date
    check_out: date
    lines: list = field(default_factory=list)   # [{"label", "nights", "rate", "amount"}]
    subtotal: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    total: Decimal = Decimal("0")

    @property
    def nights(self):
        return (self.check_out - self.check_in).days

    def as_json(self):
        return [{**line, "rate": str(line["rate"]), "amount": str(line["amount"])} for line in self.lines]


def quote(unit_type, check_in: date, check_out: date) -> Quote:
    nights = (check_out - check_in).days
    if nights < 1:
        raise PricingError("Check-out must be after check-in.")
    if nights < unit_type.min_nights:
        raise PricingError(f"Minimum stay is {unit_type.min_nights} nights.")
    if nights > MAX_NIGHTS:
        raise PricingError(f"For stays over {MAX_NIGHTS} nights, please call us.")

    rules = list(
        unit_type.rate_rules.filter(dates__overlap=DateRange(check_in, check_out, "[)")).order_by("-priority", "-id")
    )

    # Group consecutive nights with the same rate into invoice lines.
    lines = []
    night = check_in
    while night < check_out:
        rule = next((r for r in rules if night in r.dates), None)
        rate = rule.nightly_rate if rule else unit_type.base_rate
        label = rule.name if rule else "Standard rate"
        if lines and lines[-1]["rate"] == rate and lines[-1]["label"] == label:
            lines[-1]["nights"] += 1
        else:
            lines.append({"label": label, "nights": 1, "rate": rate})
        night += timedelta(days=1)

    for line in lines:
        line["amount"] = line["rate"] * line["nights"]

    subtotal = sum((line["amount"] for line in lines), Decimal("0"))
    tax = (subtotal * settings.TAX_RATE).quantize(Decimal("0.01"))
    return Quote(check_in, check_out, lines, subtotal, tax, subtotal + tax)
