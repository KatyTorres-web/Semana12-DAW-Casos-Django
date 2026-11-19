"""Rutas de la app rrhh.

Los nombres (name=...) los usa el middleware de horario y de auditoría: no cambiarlos.
"""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.panel, name="panel"),
    path("asistencia/marcar/", views.marcar_asistencia, name="marcar_asistencia"),
    path("asistencia/", views.mis_asistencias, name="mis_asistencias"),
    path("asistencia/<int:pk>/corregir/", views.asistencia_corregir, name="asistencia_corregir"),
    path("permisos/", views.mis_permisos, name="mis_permisos"),
    path("permisos/nuevo/", views.permiso_nuevo, name="permiso_nuevo"),
    path("permisos/pendientes/", views.permisos_pendientes, name="permisos_pendientes"),
    path("permisos/<int:pk>/revisar/", views.permiso_revisar, name="permiso_revisar"),
    path("reportes/asistencia/", views.reporte_asistencia, name="reporte_asistencia"),
]
