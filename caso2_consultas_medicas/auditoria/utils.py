"""Funciones de apoyo para registrar eventos de auditoría."""
import logging

logger = logging.getLogger("auditoria")


def obtener_ip(request):
    """IP del cliente (considera proxies)."""
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def registrar_evento(request, accion, detalle="", nivel="INFO", usuario=None, codigo=None):
    """Guarda el evento en la base de datos y lo escribe en el log."""
    from .models import RegistroAuditoria

    if usuario is None and getattr(request, "user", None) and request.user.is_authenticated:
        usuario = request.user
    nombre = usuario.username if usuario else "anónimo"
    ip = obtener_ip(request)
    ruta = getattr(request, "path", "")[:255]

    RegistroAuditoria.objects.create(
        usuario=usuario, nombre_usuario=nombre, ip=ip, accion=accion,
        metodo=request.method or "", ruta=ruta, codigo_respuesta=codigo,
        nivel=nivel, detalle=detalle,
    )
    logger.log(
        logging.WARNING if nivel == "WARNING" else logging.INFO,
        'usuario=%s ip=%s accion="%s" ruta=%s %s',
        nombre, ip, accion, ruta, detalle,
    )
