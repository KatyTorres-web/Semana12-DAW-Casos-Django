"""Nombres de los grupos (roles).

Este archivo es el "contrato" entre las dos integrantes: los nombres se usan
en las vistas, en los permisos y en los comandos de datos. NO cambiarlos.
"""
ADMIN = "Admins"
MEDICO = "Médicos"
RECEPCIONISTA = "Recepcionistas"
PACIENTE = "Pacientes"

TODOS = (ADMIN, MEDICO, RECEPCIONISTA, PACIENTE)
