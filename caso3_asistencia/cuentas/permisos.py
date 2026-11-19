"""Autorización jerárquica.

Roles (grupos):            Alcance de datos:
  Admin RRHH   -> todo          toda la empresa
  Jefe de Área -> su área       empleados del área que dirige
  Empleado     -> lo suyo       solo sus registros
  Contador     -> reportes      toda la empresa, solo lectura

Permisos personalizados (definidos en rrhh/models.py):
  registrar_asistencia, solicitar_permiso -> todos los empleados
  aprobar_permiso                         -> jefes y RRHH
  ver_reportes_area                       -> jefes de área
  ver_reportes_globales                   -> Admin RRHH y Contador
  corregir_asistencia                     -> solo Admin RRHH
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .roles import ADMIN_RRHH, JEFE_AREA

NOMBRES_PERMISOS = {
    "rrhh.registrar_asistencia": "registrar asistencia",
    "rrhh.solicitar_permiso": "solicitar permisos",
    "rrhh.aprobar_permiso": "aprobar permisos",
    "rrhh.ver_reportes_area": "ver reportes de área",
    "rrhh.ver_reportes_globales": "ver reportes globales",
    "rrhh.corregir_asistencia": "corregir asistencia",
}


def tiene_rol(user, *roles):
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name__in=roles).exists()


def permiso_requerido(*permisos, cualquiera=False):
    """@login_required + permisos de Django. cualquiera=True: basta con uno de ellos."""
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            tiene = [request.user.has_perm(p) for p in permisos]
            if not (any(tiene) if cualquiera else all(tiene)):
                legibles = (" o " if cualquiera else ", ").join(NOMBRES_PERMISOS.get(p, p) for p in permisos)
                raise PermissionDenied(f"No tiene permiso para {legibles}.")
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


def filtrar_por_alcance(user, queryset, campo_empleado="empleado"):
    """Restringe un queryset según la jerarquía del usuario."""
    if user.is_superuser or user.has_perm("rrhh.ver_reportes_globales") or tiene_rol(user, ADMIN_RRHH):
        return queryset
    if tiene_rol(user, JEFE_AREA):
        return queryset.filter(**{f"{campo_empleado}__area__jefe__usuario": user})
    return queryset.filter(**{f"{campo_empleado}__usuario": user})


def puede_aprobar_permiso(user, permiso):
    """RRHH aprueba cualquier permiso; el jefe solo los de su área. Nadie aprueba los suyos."""
    if not user.has_perm("rrhh.aprobar_permiso"):
        return False
    if permiso.empleado.usuario_id == user.id:
        return False
    if user.is_superuser or tiene_rol(user, ADMIN_RRHH):
        return True
    area = permiso.empleado.area
    return tiene_rol(user, JEFE_AREA) and area.jefe is not None and area.jefe.usuario_id == user.id
