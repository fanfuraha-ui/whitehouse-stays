from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Booking, Guest, Invoice, Payment


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ("provider", "reference", "amount", "status", "channel", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("reference", "branch_name", "unit", "check_in", "check_out", "guest",
                    "status", "source", "total_amount", "flag")
    list_filter = ("needs_attention", "status", "source", "unit__unit_type__branch", "unit__unit_type__bedrooms")
    search_fields = ("reference", "guest__full_name", "guest__phone", "external_uid")
    autocomplete_fields = ("guest",)
    readonly_fields = ("reference", "price_breakdown", "external_uid", "created_at", "updated_at", "invoice_link")
    list_select_related = ("unit__unit_type__branch", "guest")
    inlines = [PaymentInline]
    actions = ["mark_resolved", "cancel_bookings"]
    fieldsets = (
        (None, {"fields": ("reference", "unit", "stay", "guest", "guests", "status", "source")}),
        ("Money", {"fields": ("total_amount", "price_breakdown", "invoice_link")}),
        ("Follow-up", {"fields": ("needs_attention", "notes")}),
        ("System", {"classes": ("collapse",), "fields": ("hold_expires_at", "external_uid",
                                                          "created_at", "updated_at")}),
    )

    @admin.display(description="Branch", ordering="unit__unit_type__branch__name")
    def branch_name(self, obj):
        return obj.branch.name

    @admin.display(description="⚠", boolean=True, ordering="needs_attention")
    def flag(self, obj):
        return obj.needs_attention

    @admin.display(description="Invoice")
    def invoice_link(self, obj):
        if obj.pk and obj.status == Booking.Status.CONFIRMED:
            return format_html('<a href="{}" target="_blank">Download PDF</a>',
                               reverse("bookings:invoice_pdf", args=[obj.reference]))
        return "Available once confirmed"

    @admin.action(description="Mark selected as resolved")
    def mark_resolved(self, request, queryset):
        queryset.update(needs_attention=False)

    @admin.action(description="Cancel selected bookings")
    def cancel_bookings(self, request, queryset):
        queryset.update(status=Booking.Status.CANCELLED)


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "email", "created_at")
    search_fields = ("full_name", "phone", "email")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "booking", "provider", "amount", "status", "channel", "created_at")
    list_filter = ("status", "provider", "channel")
    search_fields = ("reference", "booking__reference")
    readonly_fields = ("raw_payload",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "booking", "issued_on", "total")
    search_fields = ("number", "booking__reference")
