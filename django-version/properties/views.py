from django.db.models import Count, Max, Min, Q
from django.shortcuts import get_object_or_404, render

from bookings.forms import SearchForm
from bookings.pricing import PricingError, quote
from bookings.services import free_units

from .branch_media import media_for
from .models import Branch, UnitType

APARTMENT_BLURBS = {
    1: "A calm, private space for a solo traveller or a couple. Ideal for work trips and short stays.",
    2: "Room for a small family or two colleagues, with a shared living area to unwind.",
    3: "Our largest homes, for families and groups who want to stay together.",
}


def home(request):
    branches = (
        Branch.objects.filter(is_active=True)
        .annotate(
            from_rate=Min("unit_types__base_rate", filter=Q(unit_types__is_active=True)),
            type_count=Count("unit_types", filter=Q(unit_types__is_active=True), distinct=True),
        )
    )
    branches = list(branches)
    for b in branches:
        b.card_photo = media_for(b.slug).get("card")
    apartment_types = [
        {**row, "blurb": APARTMENT_BLURBS.get(row["bedrooms"], "")}
        for row in (
            UnitType.objects.filter(is_active=True, branch__is_active=True)
            .values("bedrooms")
            .annotate(from_rate=Min("base_rate"), sleeps=Max("max_guests"))
            .order_by("bedrooms")
        )
    ]
    return render(request, "properties/home.html", {
        "branches": branches, "apartment_types": apartment_types, "form": SearchForm(),
    })


def branch_detail(request, slug):
    branch = get_object_or_404(Branch, slug=slug, is_active=True)
    unit_types = branch.unit_types.filter(is_active=True).prefetch_related("photos", "amenities")
    form = SearchForm(request.GET or None)
    searched = form.is_valid()
    media = media_for(branch.slug)
    unit_photos = media.get("units", {})

    options = []
    for unit_type in unit_types:
        option = {"unit_type": unit_type, "available": None, "quote": None, "reason": "",
                  "photo": unit_photos.get(unit_type.bedrooms)}
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
        {"branch": branch, "form": form, "searched": searched, "options": options, "media": media,
         "all_branches": Branch.objects.filter(is_active=True)},
    )
