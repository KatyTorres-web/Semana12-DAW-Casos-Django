"""Señales de autenticación: auditan logins, logouts e intentos fallidos."""
from django.contrib import messages
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from auditoria.utils import registrar_evento


@receiver(user_logged_in)
def al_iniciar_sesion(sender, request, user, **kwargs):
    registrar_evento(request, "Inicio de sesión", usuario=user)


@receiver(user_logged_out)
def al_cerrar_sesion(sender, request, user, **kwargs):
    if user:
        if getattr(request, "cierre_por_inactividad", False):
            registrar_evento(request, "Cierre de sesión por inactividad", usuario=user)
        else:
            registrar_evento(request, "Cierre de sesión", usuario=user)
            messages.info(request, "Cerraste sesión correctamente.")


@receiver(user_login_failed)
def al_fallar_login(sender, credentials, request=None, **kwargs):
    if request is not None:
        registrar_evento(
            request,
            "Intento de inicio de sesión fallido",
            detalle=f"usuario intentado: {credentials.get('username', '?')}",
            nivel="WARNING",
        )
