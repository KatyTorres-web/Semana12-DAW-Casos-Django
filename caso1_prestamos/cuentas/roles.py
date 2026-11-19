"""Nombres de los roles (grupos de Django).

Este archivo es el "contrato" entre las dos integrantes: los nombres se usan
en las vistas, en los permisos y en los comandos de datos. NO cambiarlos.
"""
ADMIN = "Administrador"
DOCENTE = "Docente"
ASISTENTE = "Asistente"

TODOS = (ADMIN, DOCENTE, ASISTENTE)
