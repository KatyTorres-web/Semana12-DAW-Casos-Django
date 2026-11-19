"""Rutas principales del proyecto."""
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "TecnoAndes S.A.C. - Recursos Humanos"
admin.site.site_title = "RRHH TecnoAndes"
admin.site.index_title = "Operaciones de RRHH"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuentas/", include("cuentas.urls")),
    path("", include("rrhh.urls")),
]
