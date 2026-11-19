"""Rutas de la app prestamos.

Los nombres (name=...) son usados por el middleware de auditoría: no cambiarlos.
"""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.catalogo, name="catalogo"),
    path("prestamos/", views.prestamo_lista, name="prestamo_lista"),
    path("prestamos/nuevo/", views.prestamo_nuevo, name="prestamo_nuevo"),
    path("prestamos/<int:pk>/devolver/", views.prestamo_devolver, name="prestamo_devolver"),
    path("equipos/<int:pk>/eliminar/", views.equipo_eliminar, name="equipo_eliminar"),
]
