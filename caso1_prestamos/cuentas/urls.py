"""Rutas de autenticación (versión base: las de Django)."""
from django.urls import include, path

urlpatterns = [
    path("", include("django.contrib.auth.urls")),
]
