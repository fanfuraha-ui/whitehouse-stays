from django.contrib import admin
from django.utils.html import format_html

from .models import Amenity, Branch, CalendarFeed, RateRule, Unit, UnitType, UnitTypePhoto


class UnitTypeInline(admin.TabularInline):
    model = UnitType
    extra = 0
    fields = ("bedrooms", "name", "max_guests", "base_rate", "min_nights", "is_active")
    show_change_link = True


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "town", "landmark", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [UnitTypeInline]


class UnitInline(admin.TabularInline):
    model = Unit
    extra = 1
    fields = ("label", "is_active", "export_feed")
    readonly_fields = ("export_feed",)

    @admin.display(description="iCal export URL (paste into Airbnb/Booking.com)")
    def export_feed(self, obj):
        if not obj.pk:
            return "—"
        return obj.get_ical_export_url()


class PhotoInline(admin.TabularInline):
    model = UnitTypePhoto
    extra = 1


class RateRuleInline(admin.TabularInline):
    model = RateRule
    extra = 0


@admin.register(UnitType)
class UnitTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "branch", "bedrooms", "base_rate", "unit_count", "is_active")
    list_filter = ("branch", "bedrooms", "is_active")
    filter_horizontal = ("amenities",)
    inlines = [UnitInline, RateRuleInline, PhotoInline]

    @admin.display(description="Units")
    def unit_count(self, obj):
        return obj.units.filter(is_active=True).count()


class CalendarFeedInline(admin.TabularInline):
    model = CalendarFeed
    extra = 0
    readonly_fields = ("last_synced_at", "last_error")


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("__str__", "unit_type", "is_active", "export_link")
    list_filter = ("unit_type__branch", "unit_type__bedrooms", "is_active")
    search_fields = ("label",)
    inlines = [CalendarFeedInline]

    @admin.display(description="iCal export")
    def export_link(self, obj):
        return format_html('<a href="{}">feed</a>', obj.get_ical_export_url())


admin.site.register(Amenity)
