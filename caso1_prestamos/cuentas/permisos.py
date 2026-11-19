"""Control de acceso por rol.

Versión BASE: solo exige iniciar sesión. La Integrante 2 reemplaza este
archivo con la verificación real de roles. Las vistas de la Integrante 1 ya
usan estas funciones, así que funcionan antes y después del cambio.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin


def tiene_rol(user, *roles):
    """Versión base: cualquier usuario autenticado."""
    return user.is_authenticated


def rol_requerido(*roles):
    """Versión base: equivale a @login_required."""
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


class RolRequeridoMixin(LoginRequiredMixin):
    roles = ()
