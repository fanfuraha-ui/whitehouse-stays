from django.urls import path

from . import views

app_name = "properties"

urlpatterns = [
    path("", views.home, name="home"),
    path("stays/<slug:slug>/", views.branch_detail, name="branch"),
]
