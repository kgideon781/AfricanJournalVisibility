from django.urls import path

from .views import OaiView


urlpatterns = [
    path("", OaiView.as_view(), name="oai"),
]
