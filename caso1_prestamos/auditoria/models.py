"""Registro de auditoría de acciones críticas y accesos."""
from django.conf import settings
from django.db import models


class RegistroAuditoria(models.Model):
    class Nivel(models.TextChoices):
        INFO = "INFO", "Información"
        WARNING = "WARNING", "Advertencia"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="registros_auditoria",
    )
    nombre_usuario = models.CharField("usuario", max_length=150)
    fecha = models.DateTimeField("fecha y hora", auto_now_add=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    accion = models.CharField("acción", max_length=120)
    metodo = models.CharField("método", max_length=10, blank=True)
    ruta = models.CharField("ruta", max_length=255, blank=True)
    codigo_respuesta = models.PositiveSmallIntegerField("HTTP", null=True, blank=True)
    nivel = models.CharField("nivel", max_length=10, choices=Nivel.choices, default=Nivel.INFO)
    detalle = models.TextField("detalle", blank=True)

    class Meta:
        verbose_name = "registro de auditoría"
        verbose_name_plural = "registros de auditoría"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y %H:%M} {self.nombre_usuario}: {self.accion}"
