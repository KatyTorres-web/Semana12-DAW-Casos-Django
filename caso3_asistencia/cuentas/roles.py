"""Nombres de los grupos (roles jerárquicos).

Este archivo es el "contrato" entre las dos integrantes: los nombres se usan
en las vistas, en los permisos y en los comandos de datos. NO cambiarlos.
"""
ADMIN_RRHH = "Admin RRHH"
JEFE_AREA = "Jefe de Área"
EMPLEADO = "Empleado"
CONTADOR = "Contador"

TODOS = (ADMIN_RRHH, JEFE_AREA, EMPLEADO, CONTADOR)
