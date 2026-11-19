"""Rutas de la app consultas.

Los nombres (name=...) los usa el middleware de auditoría: no cambiarlos.
"""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.panel, name="panel"),
    path("citas/", views.cita_lista, name="cita_lista"),
    path("citas/nueva/", views.cita_nueva, name="cita_nueva"),
    path("citas/<int:pk>/cancelar/", views.cita_cancelar, name="cita_cancelar"),
    path("citas/<int:pk>/consulta/", views.consulta_registrar, name="consulta_registrar"),
    path("pacientes/nuevo/", views.paciente_nuevo, name="paciente_nuevo"),
    path("pacientes/<int:pk>/historial/", views.historial, name="historial_paciente"),
    path("consultas/<int:pk>/nota/", views.nota_agregar, name="nota_agregar"),
    path("reportes/", views.reportes, name="reportes"),
]
