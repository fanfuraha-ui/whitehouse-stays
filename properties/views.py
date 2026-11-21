from django.db.models import Count, Min, Q
from django.shortcuts import get_object_or_404, render

from bookings.forms import SearchForm
from bookings.pricing import PricingError, quote
from bookings.services import free_units

from .models import Branch


def home(request):
    branches = (
        Branch.objects.filter(is_active=True)
        .annotate(
            from_rate=Min("unit_types__base_rate", filter=Q(unit_types__is_active=True)),
            type_count=Count("unit_types", filter=Q(unit_types__is_active=True), distinct=True),
        )
    )
    return render(request, "properties/home.html", {"branches": branches, "form": SearchForm()})


def branch_detail(request, slug):
    branch = get_object_or_404(Branch, slug=slug, is_active=True)
    unit_types = branch.unit_types.filter(is_active=True).prefetch_related("photos", "amenities")
    form = SearchForm(request.GET or None)
    searched = form.is_valid()

    options = []
    for unit_type in unit_types:
        option = {"unit_type": unit_type, "available": None, "quote": None, "reason": ""}
        if searched:
            data = form.cleaned_data
            if data["guests"] > unit_type.max_guests:
                option["reason"] = f"Sleeps up to {unit_type.max_guests}"
            else:
                try:
                    option["quote"] = quote(unit_type, data["check_in"], data["check_out"])
                    option["available"] = free_units(unit_type, data["check_in"], data["check_out"]).count()
                    if not option["available"]:
                        option["reason"] = "Fully booked for these dates"
                except PricingError as exc:
                    option["reason"] = str(exc)
        options.append(option)

    return render(
        request,
        "properties/branch_detail.html",
        {"branch": branch, "form": form, "searched": searched, "options": options},
    )
