"""Rutas principales del proyecto."""
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Centro Médico Universitario - UNCP"
admin.site.site_title = "Centro Médico UNCP"
admin.site.index_title = "Gestión operativa"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuentas/", include("cuentas.urls")),
    path("", include("consultas.urls")),
]
