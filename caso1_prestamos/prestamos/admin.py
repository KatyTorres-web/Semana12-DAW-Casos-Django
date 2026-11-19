"""Django Admin personalizado."""
import logging

from django.conf import settings
from django.contrib import admin, messages
from django.core.mail import send_mail
from django.db.models import Count
from django.utils import timezone
from django.utils.html import format_html

from .models import Equipo, Laboratorio, Prestamo

logger = logging.getLogger("auditoria")

COLORES_ESTADO = {"operativo": "#198754", "mantenimiento": "#e0a800", "baja": "#6c757d"}


@admin.register(Laboratorio)
class LaboratorioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "ubicacion", "total_equipos")
    search_fields = ("nombre",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_equipos=Count("equipos"))

    @admin.display(description="Equipos", ordering="num_equipos")
    def total_equipos(self, obj):
        return obj.num_equipos


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo_patrimonial", "nombre", "marca", "categoria", "laboratorio",
        "estado_visual", "cantidad_total", "dias_mantenimiento",
    )
    list_filter = ("laboratorio", "estado", "categoria")
    search_fields = ("codigo_patrimonial", "nombre", "categoria", "marca")
    list_select_related = ("laboratorio",)
    list_per_page = 20
    actions = ["marcar_en_mantenimiento"]

    @admin.display(description="Estado", ordering="estado")
    def estado_visual(self, obj):
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:12px;">{}</span>',
            COLORES_ESTADO[obj.estado], obj.get_estado_display(),
        )

    @admin.display(description="Días desde mantenimiento", ordering="fecha_ultimo_mantenimiento")
    def dias_mantenimiento(self, obj):
        dias = obj.dias_desde_mantenimiento
        if dias is None:
            return "Sin registro"
        color = "#dc3545" if dias > 180 else "#212529"
        return format_html('<span style="color:{};">{} días</span>', color, dias)

    @admin.action(description="Marcar como en mantenimiento")
    def marcar_en_mantenimiento(self, request, queryset):
        total = queryset.exclude(estado=Equipo.Estado.BAJA).update(
            estado=Equipo.Estado.MANTENIMIENTO,
            fecha_ultimo_mantenimiento=timezone.localdate(),
        )
        self.message_user(request, f"{total} equipo(s) marcados en mantenimiento.", messages.SUCCESS)


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = (
        "id", "docente_nombre", "equipo", "cantidad", "fecha_prestamo",
        "fecha_devolucion_prevista", "estado", "dias_de_retraso", "recordatorio_enviado",
    )
    list_filter = (
        "estado", "fecha_prestamo", "fecha_devolucion_prevista",
        ("docente", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        "equipo__codigo_patrimonial", "equipo__nombre",
        "docente__username", "docente__first_name", "docente__last_name",
    )
    list_select_related = ("docente", "equipo")
    date_hierarchy = "fecha_prestamo"
    autocomplete_fields = ("equipo",)
    readonly_fields = ("creado_en", "registrado_por")
    actions = ["enviar_recordatorio"]

    @admin.display(description="Docente", ordering="docente__last_name")
    def docente_nombre(self, obj):
        return obj.docente.get_full_name() or obj.docente.username

    @admin.display(description="Días de retraso")
    def dias_de_retraso(self, obj):
        dias = obj.dias_retraso
        if dias == 0:
            return "-"
        return format_html('<strong style="color:#dc3545;">{} días</strong>', dias)

    @admin.action(description="Enviar recordatorio de devolución")
    def enviar_recordatorio(self, request, queryset):
        activos = queryset.filter(estado=Prestamo.Estado.ACTIVO).select_related("docente", "equipo")
        for p in activos:
            correo = p.docente.email or f"{p.docente.username}@uncp.edu.pe"
            send_mail(
                subject=f"Recordatorio: devolver {p.equipo.nombre}",
                message=(
                    f"Estimado(a) {p.docente.get_full_name() or p.docente.username}:\n"
                    f"Recuerde devolver {p.cantidad} x {p.equipo.nombre} "
                    f"({p.equipo.codigo_patrimonial}) antes del "
                    f"{p.fecha_devolucion_prevista:%d/%m/%Y}.\n"
                    f"Días de retraso: {p.dias_retraso}."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[correo],
                fail_silently=True,
            )
            logger.info("Recordatorio de devolución enviado a %s (préstamo #%s)", correo, p.pk)
        enviados = activos.update(recordatorio_enviado=True)
        omitidos = queryset.count() - enviados
        self.message_user(request, f"Recordatorio enviado a {enviados} préstamo(s) activo(s).", messages.SUCCESS)
        if omitidos:
            self.message_user(request, f"{omitidos} préstamo(s) ya devueltos fueron omitidos.", messages.WARNING)
