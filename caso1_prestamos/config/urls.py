"""Rutas principales del proyecto."""
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Préstamos de Equipos - FIS UNCP"
admin.site.site_title = "Préstamos FIS"
admin.site.index_title = "Panel del Jefe de Laboratorio"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuentas/", include("cuentas.urls")),
    path("", include("prestamos.urls")),
]
