"""Autorización por rol (grupos de Django).

Las vistas usan:
    @rol_requerido(ADMIN, ASISTENTE)
    class MiVista(RolRequeridoMixin, View): roles = (ADMIN,)

Si el usuario no inició sesión -> redirige al login.
Si inició sesión pero no tiene el rol -> 403 (lo registra el middleware).
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


def tiene_rol(user, *roles):
    """True si el usuario pertenece a alguno de los grupos (el superusuario siempre)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=roles).exists()


def rol_requerido(*roles):
    """Decorador para vistas basadas en funciones."""
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            if not tiene_rol(request.user, *roles):
                raise PermissionDenied(
                    "Esta acción requiere el rol: " + " o ".join(roles) + "."
                )
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


class RolRequeridoMixin(LoginRequiredMixin):
    """Equivalente para vistas basadas en clases."""

    roles = ()

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not tiene_rol(request.user, *self.roles):
            raise PermissionDenied("Esta acción requiere el rol: " + " o ".join(self.roles) + ".")
        return super().dispatch(request, *args, **kwargs)
