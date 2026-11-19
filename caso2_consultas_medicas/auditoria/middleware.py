"""Middleware especializado del Centro Médico.

Orden en settings.MIDDLEWARE (después de Auth y Messages):
  1. SesionInactivaMiddleware     -> cierra la sesión tras 20 min sin actividad
  2. AlertasCitasMiddleware       -> al iniciar sesión, avisa al médico sus citas pendientes
  3. HorarioAtencionMiddleware    -> bloquea citas fuera del horario (L-V 8-18, Sáb 8-13)
  4. AuditoriaMedicaMiddleware    -> registra accesos a historiales y todo cambio de datos
  5. AccesoNoAutorizadoMiddleware -> registra 403 y accesos sin autenticación
"""
import time
from datetime import datetime, timedelta
from datetime import time as hora

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from .utils import logger, registrar_evento

DURACION_CITA = timedelta(minutes=30)
# día de la semana (0 = lunes) -> (apertura, cierre)
HORARIO_ATENCION = {d: (hora(8, 0), hora(18, 0)) for d in range(5)}
HORARIO_ATENCION[5] = (hora(8, 0), hora(13, 0))
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Cambios de datos que se auditan (nombre de ruta -> descripción)
CAMBIOS = {
    "cita_nueva": "Agendamiento de cita",
    "cita_cancelar": "Cancelación de cita",
    "consulta_registrar": "Registro de consulta médica",
    "nota_agregar": "Nota agregada a una consulta",
    "paciente_nuevo": "Registro de paciente",
}


def _modelo(app, nombre):
    try:
        return apps.get_model(app, nombre)
    except LookupError:
        return None


class SesionInactivaMiddleware:
    """Cierra la sesión si pasaron más de N segundos desde la última petición."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.limite = getattr(settings, "SESSION_INACTIVIDAD_SEGUNDOS", 1200)

    def __call__(self, request):
        if request.user.is_authenticated:
            ahora = time.time()
            ultima = request.session.get("ultima_actividad")
            if ultima and ahora - ultima > self.limite:
                usuario = request.user.username
                request.cierre_por_inactividad = True
                logout(request)
                logger.info("usuario=%s sesión cerrada por inactividad (%s min)", usuario, self.limite // 60)
                messages.warning(request, "Tu sesión expiró por inactividad (20 minutos). Vuelve a iniciar sesión.")
                return redirect(f"{reverse('login')}?next={request.path}")
            request.session["ultima_actividad"] = ahora
        return self.get_response(request)


class AlertasCitasMiddleware:
    """Primera petición de la sesión: si el usuario es médico, le avisa sus citas pendientes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.session.get("alerta_citas_revisada"):
            request.session["alerta_citas_revisada"] = True
            Medico, Cita = _modelo("consultas", "Medico"), _modelo("consultas", "Cita")
            medico = Medico.objects.filter(usuario=request.user).first() if Medico else None
            if medico:
                pendientes = Cita.objects.filter(medico=medico, estado="pendiente")
                hoy = pendientes.filter(fecha_hora__date=timezone.localdate()).count()
                total = pendientes.filter(fecha_hora__gte=timezone.now()).count()
                if hoy or total:
                    texto = f"Tienes {hoy} cita(s) pendiente(s) para hoy"
                    if total:
                        texto += f" y {total} próxima(s) en tu agenda"
                    messages.info(request, texto + ".")
                    logger.info("usuario=%s alerta: %s cita(s) hoy, %s próximas", request.user.username, hoy, total)
        return self.get_response(request)


class HorarioAtencionMiddleware:
    """Antes de llegar a la vista, rechaza citas fuera del horario de atención."""

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def verificar(fecha_hora):
        dia = fecha_hora.weekday()
        if dia not in HORARIO_ATENCION:
            return "El Centro Médico no atiende los domingos."
        apertura, cierre = HORARIO_ATENCION[dia]
        fin = (fecha_hora + DURACION_CITA).time()
        if fecha_hora.time() < apertura or fin > cierre or fin < apertura:
            return (
                f"Fuera del horario de atención: los {DIAS[dia]} se atiende de "
                f"{apertura:%H:%M} a {cierre:%H:%M} (la cita de 30 minutos debe terminar antes del cierre)."
            )
        return None

    def __call__(self, request):
        if request.method == "POST":
            try:
                nombre = resolve(request.path_info).url_name
            except Resolver404:
                nombre = None
            if nombre == "cita_nueva":
                try:
                    fecha_hora = datetime.strptime(request.POST.get("fecha_hora", ""), "%Y-%m-%dT%H:%M")
                except ValueError:
                    fecha_hora = None  # formato inválido: lo valida el formulario
                error = self.verificar(fecha_hora) if fecha_hora else None
                if error:
                    registrar_evento(
                        request, "Cita fuera de horario bloqueada",
                        detalle=f"fecha solicitada={fecha_hora:%d/%m/%Y %H:%M}", nivel="WARNING",
                    )
                    messages.error(request, error)
                    return redirect(request.get_full_path())
        return self.get_response(request)


class AuditoriaMedicaMiddleware:
    """Registra quién accedió a qué historial clínico y todo cambio de datos (quién, cuándo, qué)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        match = request.resolver_match
        if not match or response.status_code == 403:  # los 403 los registra el siguiente middleware
            return response

        nombre = match.url_name or ""
        if request.method == "GET" and nombre == "historial_paciente" and response.status_code == 200:
            registrar_evento(
                request, "Acceso a historial clínico",
                detalle=f"paciente_id={match.kwargs.get('pk')}", codigo=200,
            )
        elif request.method == "POST":
            accion = CAMBIOS.get(nombre)
            if accion is None and match.namespace == "admin" and nombre.rsplit("_", 1)[-1] in ("add", "change", "delete", "changelist"):
                accion = f"Cambio desde el admin ({nombre})"
            if accion:
                exito = response.status_code in (301, 302)
                registrar_evento(
                    request,
                    accion if exito else f"{accion} (rechazado)",
                    detalle=f"{match.kwargs or ''} resultado=HTTP {response.status_code}".strip(),
                    nivel="INFO" if exito else "WARNING",
                    codigo=response.status_code,
                )
        return response


class AccesoNoAutorizadoMiddleware:
    """Registra respuestas 403 y redirecciones al login de usuarios sin sesión."""

    def __init__(self, get_response):
        self.get_response = get_response

    def process_exception(self, request, exception):
        """Guarda el motivo del PermissionDenied para el registro de auditoría."""
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
