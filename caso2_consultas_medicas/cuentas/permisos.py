"""Autorización con permisos granulares y reglas de propiedad.

Permisos personalizados (definidos en consultas/models.py):
  consultas.ver_historial_clinico -> médicos (y el propio paciente, por regla de propiedad)
  consultas.agendar_cita          -> recepcionistas y pacientes
  consultas.cancelar_cita         -> recepcionistas, médicos y el propio paciente
  consultas.generar_reportes      -> administradores
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .roles import ADMIN, MEDICO, PACIENTE, RECEPCIONISTA

NOMBRES_PERMISOS = {
    "consultas.ver_historial_clinico": "ver historiales clínicos",
    "consultas.agendar_cita": "agendar citas",
    "consultas.cancelar_cita": "cancelar citas",
    "consultas.generar_reportes": "generar reportes",
    "consultas.add_consulta": "registrar consultas médicas",
    "consultas.add_notaconsulta": "agregar notas a consultas",
    "consultas.add_paciente": "registrar pacientes",
}


def tiene_rol(user, *roles):
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name__in=roles).exists()


def permiso_requerido(*permisos):
    """@login_required + verificación de permisos de Django (403 si falta alguno)."""
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            faltantes = [p for p in permisos if not request.user.has_perm(p)]
            if faltantes:
                legibles = ", ".join(NOMBRES_PERMISOS.get(p, p) for p in faltantes)
                raise PermissionDenied(f"No tiene permiso para {legibles}.")
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


def puede_ver_historial(user, paciente):
    """Solo médicos (permiso ver_historial_clinico) y el propio paciente."""
    if not user.is_authenticated:
        return False
    if user.has_perm("consultas.ver_historial_clinico"):
        return True
    return paciente.usuario_id is not None and paciente.usuario_id == user.id


def puede_cancelar_cita(user, cita):
    """Recepcionistas y admins: cualquiera. Médicos: las suyas. Pacientes: las propias."""
    if not user.has_perm("consultas.cancelar_cita"):
        return False
    if tiene_rol(user, ADMIN, RECEPCIONISTA):
        return True
    if tiene_rol(user, MEDICO) and cita.medico.usuario_id == user.id:
        return True
    if tiene_rol(user, PACIENTE) and cita.paciente.usuario_id == user.id:
        return True
    return False
