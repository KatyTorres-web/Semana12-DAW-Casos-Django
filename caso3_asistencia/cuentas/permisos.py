"""Control de acceso jerárquico.

Versión BASE: solo exige iniciar sesión y deja pasar todo. La Integrante 2
reemplaza este archivo con los permisos reales. Las vistas de la Integrante 1
ya usan estas funciones, así que funcionan antes y después del cambio.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required


def permiso_requerido(*permisos, cualquiera=False):
    """Versión base: equivale a @login_required."""
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


def filtrar_por_alcance(user, queryset, campo_empleado="empleado"):
    """Versión base: devuelve todo."""
    return queryset


def puede_aprobar_permiso(user, permiso):
    """Versión base: cualquier usuario autenticado."""
    return user.is_authenticated
