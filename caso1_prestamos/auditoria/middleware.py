"""Middleware propio del sistema de préstamos.

Orden en settings.MIDDLEWARE (después de Auth y Messages):
  1. SesionInactivaMiddleware      -> cierra la sesión tras 30 min sin actividad
  2. PrestamosVencidosMiddleware   -> alerta de préstamos vencidos al iniciar sesión
  3. AuditoriaMiddleware           -> registra préstamos, devoluciones y eliminaciones
  4. AccesoNoAutorizadoMiddleware  -> registra accesos denegados (403 o sin login)
"""
import time

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .utils import logger, registrar_evento

# Nombres de ruta (name=...) de la app prestamos que se consideran críticos
ACCIONES_CRITICAS = {
    "prestamo_nuevo": "Registro de préstamo",
    "prestamo_devolver": "Registro de devolución",
    "equipo_eliminar": "Eliminación de equipo",
}


class SesionInactivaMiddleware:
    """Cierra la sesión si pasaron más de N segundos desde la última petición."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.limite = getattr(settings, "SESSION_INACTIVIDAD_SEGUNDOS", 1800)

    def __call__(self, request):
        if request.user.is_authenticated:
            ahora = time.time()
            ultima = request.session.get("ultima_actividad")
            if ultima and ahora - ultima > self.limite:
                usuario = request.user.username
                request.cierre_por_inactividad = True  # lo lee la señal de logout
                logout(request)
                logger.info("usuario=%s sesión cerrada por inactividad (%s min)", usuario, self.limite // 60)
                messages.warning(request, "Tu sesión expiró por inactividad. Vuelve a iniciar sesión.")
                return redirect(f"{reverse('login')}?next={request.path}")
            request.session["ultima_actividad"] = ahora
        return self.get_response(request)


class PrestamosVencidosMiddleware:
    """Al iniciar sesión, avisa al docente si tiene préstamos vencidos (una vez por sesión)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.session.get("alerta_vencidos_revisada"):
            request.session["alerta_vencidos_revisada"] = True
            try:
                Prestamo = apps.get_model("prestamos", "Prestamo")
            except LookupError:
                Prestamo = None
            if Prestamo is not None:
                vencidos = Prestamo.objects.filter(
                    docente=request.user, estado="activo",
                    fecha_devolucion_prevista__lt=timezone.localdate(),
                ).count()
                if vencidos:
                    messages.warning(
                        request,
                        f"Tienes {vencidos} préstamo(s) vencido(s). "
                        "Devuelve los equipos lo antes posible.",
                    )
                    logger.info("usuario=%s alerta: %s préstamo(s) vencido(s)", request.user.username, vencidos)
        return self.get_response(request)


class AuditoriaMiddleware:
    """Registra cada acción crítica (POST) con usuario, fecha/hora, IP y resultado."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Los 403 los registra AccesoNoAutorizadoMiddleware (evita duplicados)
        if request.method == "POST" and request.resolver_match and response.status_code != 403:
            nombre = request.resolver_match.url_name or ""
            accion = ACCIONES_CRITICAS.get(nombre)
            if accion is None and nombre.endswith("_delete"):
                accion = "Eliminación desde el admin"
            if accion:
                exito = response.status_code in (301, 302)
                registrar_evento(
                    request,
                    accion if exito else f"{accion} (rechazado)",
                    detalle=f"resultado=HTTP {response.status_code}"
                    + ("" if exito else " (el formulario tenía errores de validación)"),
                    nivel="INFO" if exito else "WARNING",
                    codigo=response.status_code,
                )
        return response


class AccesoNoAutorizadoMiddleware:
    """Registra intentos de acceso no autorizado: 403 y vistas protegidas sin login."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code == 403:
            registrar_evento(
                request, "Acceso denegado (403)",
                detalle="el usuario no tiene el rol o permiso requerido",
                nivel="WARNING", codigo=403,
            )
        elif (
            response.status_code == 302
            and not request.user.is_authenticated
            and response.get("Location", "").startswith(reverse("login"))
            and request.path not in (reverse("login"), reverse("logout"))
        ):
            registrar_evento(
                request, "Acceso sin autenticación",
                detalle="redirigido al login", nivel="WARNING", codigo=302,
            )
        return response
