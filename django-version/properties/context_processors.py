from django.conf import settings

from .models import Branch


def brand(request):
    return {
        "BRAND": settings.BRAND,
        "nav_branches": Branch.objects.filter(is_active=True).only("name", "slug"),
    }
