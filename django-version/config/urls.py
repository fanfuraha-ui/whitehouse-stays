from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Whitehouse Stays — Back Office"
admin.site.site_title = "Whitehouse Stays"
admin.site.index_title = "Bookings, units and rates"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("bookings.urls")),
    path("", include("properties.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
