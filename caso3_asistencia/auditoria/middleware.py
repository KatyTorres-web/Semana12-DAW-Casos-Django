"""Middleware de control y auditoría de TecnoAndes.

Orden en settings.MIDDLEWARE (después de Auth y Messages):
  1. SesionInactivaMiddleware          -> cierra la sesión tras 45 min sin actividad
  2. BloqueoCuentaMiddleware           -> expulsa a usuarios con la cuenta desactivada
  3. RecordatorioAsistenciaMiddleware  -> al iniciar sesión en día laborable, recuerda marcar entrada
  4. HorarioMarcacionMiddleware        -> solo permite marcar a +/- 2 h del horario del empleado
  5. AuditoriaMiddleware               -> registra toda modificación de asistencia y permisos
  6. AccesoNoAutorizadoMiddleware      -> registra 403 y accesos sin autenticación
"""
import time
from datetime import datetime, timedelta

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from .utils import logger, registrar_evento

# Cambios que se auditan (nombre de ruta -> descripción)
CAMBIOS = {
    "marcar_asistencia": "Marcación de asistencia",
    "asistencia_corregir": "Corrección de asistencia",
    "permiso_nuevo": "Solicitud de permiso",
    "permiso_revisar": "Revisión de permiso",
}


def _empleado(user):
    """Empleado vinculado al usuario (None si no existe o la app no está instalada)."""
    try:
        Empleado = apps.get_model("rrhh", "Empleado")
    except LookupError:
        return None
    return Empleado.objects.filter(usuario=user).first()


class SesionInactivaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.limite = getattr(settings, "SESSION_INACTIVIDAD_SEGUNDOS", 2700)

    def __call__(self, request):
        if request.user.is_authenticated:
            ahora = time.time()
            ultima = request.session.get("ultima_actividad")
            if ultima and ahora - ultima > self.limite:
                usuario = request.user.username
                request.cierre_por_inactividad = True
                logout(request)
                logger.info("usuario=%s sesión cerrada por inactividad (%s min)", usuario, self.limite // 60)
                messages.warning(request, "Tu sesión expiró por inactividad (45 minutos). Vuelve a iniciar sesión.")
                return redirect(f"{reverse('login')}?next={request.path}")
            request.session["ultima_actividad"] = ahora
        return self.get_response(request)


class BloqueoCuentaMiddleware:
    """Si la cuenta del empleado se desactiva, se cierra su sesión en la siguiente petición."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            empleado = _empleado(request.user)
            if empleado is not None and not empleado.activo:
                registrar_evento(request, "Acceso bloqueado: cuenta desactivada", nivel="WARNING")
                request.cierre_por_bloqueo = True  # lo lee la señal de logout
                logout(request)
                messages.error(request, "Tu cuenta está desactivada. Comunícate con RRHH.")
                return redirect("login")
        return self.get_response(request)


class RecordatorioAsistenciaMiddleware:
    """Primera petición de la sesión: si es día laborable y no marcó entrada, se lo recuerda."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.session.get("recordatorio_revisado"):
            request.session["recordatorio_revisado"] = True
            hoy = timezone.localdate()
            empleado = _empleado(request.user)
            if empleado is not None and hoy.weekday() < 5 and not empleado.asistencias.filter(fecha=hoy).exists():
                messages.warning(
                    request,
                    f"Recordatorio: hoy no has marcado tu entrada (horario {empleado.hora_entrada:%H:%M}).",
                )
                logger.info("usuario=%s recordatorio: sin marcación de entrada hoy", request.user.username)
        return self.get_response(request)


class HorarioMarcacionMiddleware:
    """Solo permite marcar entrada/salida a +/- N horas del horario del empleado."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.margen = timedelta(hours=getattr(settings, "MARGEN_MARCACION_HORAS", 2))

    def __call__(self, request):
        if request.method == "POST" and getattr(settings, "VALIDAR_HORARIO_MARCACION", True) and request.user.is_authenticated:
            try:
                nombre = resolve(request.path_info).url_name
            except Resolver404:
                nombre = None
            empleado = _empleado(request.user) if nombre == "marcar_asistencia" else None
            tipo = request.POST.get("tipo")
            if empleado is not None and tipo in ("entrada", "salida"):
                ahora = timezone.localtime()
                referencia = empleado.hora_entrada if tipo == "entrada" else empleado.hora_salida
                hora_ref = timezone.make_aware(datetime.combine(ahora.date(), referencia), ahora.tzinfo)
                if abs(ahora - hora_ref) > self.margen:
                    desde = (hora_ref - self.margen).strftime("%H:%M")
                    hasta = (hora_ref + self.margen).strftime("%H:%M")
                    registrar_evento(
                        request, f"Marcación de {tipo} fuera de horario bloqueada",
                        detalle=f"hora={ahora:%H:%M} permitido={desde}-{hasta}", nivel="WARNING",
                    )
                    messages.error(request, f"Solo puedes marcar tu {tipo} entre las {desde} y las {hasta}.")
                    return redirect("panel")
        return self.get_response(request)


class AuditoriaMiddleware:
    """Registra toda modificación a asistencia y permisos (usuario, fecha/hora, IP, qué cambió)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        match = request.resolver_match
        if request.method != "POST" or not match or response.status_code == 403:
            return response

        nombre = match.url_name or ""
        accion = CAMBIOS.get(nombre)
        if nombre == "marcar_asistencia":
            accion = f"Marcación de {request.POST.get('tipo', '?')}"
        if accion is None and match.namespace == "admin" and nombre.startswith("rrhh_"):
            accion = f"Cambio desde el admin ({nombre})"
        if accion:
            exito = response.status_code in (301, 302)
            detalle = f"{match.kwargs or ''} resultado=HTTP {response.status_code}".strip()
            if nombre == "permiso_revisar":
                detalle = f"decisión={request.POST.get('decision')} {detalle}"
            registrar_evento(
                request, accion, detalle=detalle,
                nivel="INFO" if exito else "WARNING", codigo=response.status_code,
            )
        return response


class AccesoNoAutorizadoMiddleware:
    """Registra respuestas 403 (con el motivo) y redirecciones al login de usuarios sin sesión."""

    def __init__(self, get_response):
        self.get_response = get_response

    def process_exception(self, request, exception):
        if isinstance(exception, PermissionDenied):
            request.motivo_denegacion = str(exception)

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 403:
            registrar_evento(
                request, "Acceso denegado (403)",
                detalle=getattr(request, "motivo_denegacion", "") or "sin el permiso requerido",
                nivel="WARNING", codigo=403,
            )
        elif (
            response.status_code == 302
            and not request.user.is_authenticated
            and response.get("Location", "").startswith(reverse("login"))
            and request.path not in (reverse("login"), reverse("logout"))
        ):
            registrar_evento(
                request, "Acceso sin autenticación", detalle="redirigido al login",
                nivel="WARNING", codigo=302,
            )
        return response
