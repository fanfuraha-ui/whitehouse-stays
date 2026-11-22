from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("book/<int:unit_type_id>/", views.checkout, name="checkout"),
    path("payments/return/", views.payment_return, name="payment_return"),
    path("payments/paystack/webhook/", views.paystack_webhook, name="paystack_webhook"),
    path("booking/<str:reference>/", views.confirmation, name="confirmation"),
    path("calendar/<uuid:token>.ics", views.ical_export, name="ical_export"),
    path("invoice/<str:reference>.pdf", views.invoice_pdf, name="invoice_pdf"),
]
