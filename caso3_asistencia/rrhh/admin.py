"""Django Admin para las operaciones de RRHH."""
from django.contrib import admin, messages
from django.db.models import Count, Prefetch
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .forms import EmpleadoForm
from .models import Area, Asistencia, CorreccionAsistencia, Empleado, Permiso
from .reportes import exportar_texto

COLORES = {"pendiente": "#e0a800", "aprobado": "#198754", "rechazado": "#dc3545"}


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "jefe", "total_empleados")
    autocomplete_fields = ("jefe",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("jefe").annotate(num=Count("empleados"))

    @admin.display(description="Empleados", ordering="num")
    def total_empleados(self, obj):
        return obj.num


@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    form = EmpleadoForm
    list_display = (
        "dni", "nombre", "cargo", "area", "tipo_contrato", "antiguedad",
        "vacaciones_disponibles", "horas_extra_mes", "activo",
    )
    list_filter = ("area", "tipo_contrato", "activo")
    search_fields = ("dni", "nombres", "apellidos", "cargo")
    list_select_related = ("area",)

    def get_queryset(self, request):
        inicio_mes = timezone.localdate().replace(day=1)
        return super().get_queryset(request).prefetch_related(
            Prefetch("asistencias", queryset=Asistencia.objects.filter(fecha__gte=inicio_mes), to_attr="asistencias_mes"),
            Prefetch("permisos", queryset=Permiso.objects.filter(tipo="vacaciones", estado="aprobado")),
        )

    def get_exclude(self, request, obj=None):
        """Confidencialidad: el salario solo lo ve RRHH."""
        if request.user.has_perm("rrhh.change_empleado"):
            return ()
        return ("salario",)

    @admin.display(description="Empleado", ordering="apellidos")
    def nombre(self, obj):
        return obj.nombre_completo

    @admin.display(description="Vacaciones disponibles")
    def vacaciones_disponibles(self, obj):
        anio = timezone.localdate().year
        tomados = sum(p.dias for p in obj.permisos.all() if p.fecha_inicio.year == anio)
        return f"{30 - tomados} días"

    @admin.display(description="Horas extra (mes)")
    def horas_extra_mes(self, obj):
        total = sum(a.horas_extra for a in obj.asistencias_mes)
        if not total:
            return "-"
        return format_html('<strong style="color:#0d6efd;">{} h</strong>', total)


class CorreccionInline(admin.TabularInline):
    model = CorreccionAsistencia
    extra = 0
    can_delete = False
    readonly_fields = ("motivo", "justificacion", "entrada_anterior", "salida_anterior",
                       "entrada_nueva", "salida_nueva", "corregido_por", "fecha")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    """Asistencia diaria con filtros por área y fecha."""

    list_display = ("fecha", "empleado", "area", "entrada", "salida", "horas", "extra", "corregida")
    list_filter = ("fecha", "empleado__area", "corregida")
    search_fields = ("empleado__dni", "empleado__nombres", "empleado__apellidos")
    date_hierarchy = "fecha"
    list_select_related = ("empleado__area",)
    actions = ["exportar_texto"]
    inlines = [CorreccionInline]

    @admin.display(description="Área", ordering="empleado__area__nombre")
    def area(self, obj):
        return obj.empleado.area

    @admin.display(description="Entrada", ordering="hora_entrada")
    def entrada(self, obj):
        return timezone.localtime(obj.hora_entrada).strftime("%H:%M")

    @admin.display(description="Salida")
    def salida(self, obj):
        return timezone.localtime(obj.hora_salida).strftime("%H:%M") if obj.hora_salida else "Sin marcar"

    @admin.display(description="Horas")
    def horas(self, obj):
        return obj.horas_trabajadas or "-"

    @admin.display(description="Horas extra")
    def extra(self, obj):
        if not obj.horas_extra:
            return "-"
        return format_html('<strong style="color:#0d6efd;">+{} h</strong>', obj.horas_extra)

    @admin.action(description="Exportar seleccionados a texto (planilla)")
    def exportar_texto(self, request, queryset):
        texto = exportar_texto(queryset.select_related("empleado__area"), "EXPORTACIÓN PARA PLANILLA - TecnoAndes S.A.C.")
        respuesta = HttpResponse(texto, content_type="text/plain; charset=utf-8")
        respuesta["Content-Disposition"] = 'attachment; filename="asistencia_planilla.txt"'
        return respuesta


@admin.register(Permiso)
class PermisoAdmin(admin.ModelAdmin):
    list_display = ("empleado", "area", "tipo", "fecha_inicio", "fecha_fin", "dias", "estado_visual", "revisado_por")
    list_filter = ("estado", "tipo", "empleado__area")
    search_fields = ("empleado__dni", "empleado__nombres", "empleado__apellidos")
    list_select_related = ("empleado__area", "revisado_por")
    readonly_fields = ("revisado_por", "fecha_revision", "creado_en")
    actions = ["aprobar_seleccionados"]

    @admin.display(description="Área", ordering="empleado__area__nombre")
    def area(self, obj):
        return obj.empleado.area

    @admin.display(description="Estado", ordering="estado")
    def estado_visual(self, obj):
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:12px;">{}</span>',
            COLORES[obj.estado], obj.get_estado_display(),
        )

    @admin.action(description="Aprobar permisos seleccionados")
    def aprobar_seleccionados(self, request, queryset):
        aprobados, omitidos = 0, []
        for permiso in queryset.filter(estado=Permiso.Estado.PENDIENTE).select_related("empleado"):
            if permiso.tipo == Permiso.Tipo.VACACIONES and permiso.dias > permiso.empleado.dias_vacaciones_disponibles:
                omitidos.append(str(permiso.empleado))
                continue
            permiso.resolver(True, request.user, "Aprobado desde el panel de RRHH")
            aprobados += 1
        self.message_user(request, f"{aprobados} permiso(s) aprobados.", messages.SUCCESS)
        if omitidos:
            self.message_user(request, f"Sin días de vacaciones suficientes: {', '.join(omitidos)}.", messages.WARNING)


@admin.register(CorreccionAsistencia)
class CorreccionAsistenciaAdmin(admin.ModelAdmin):
    list_display = ("asistencia", "motivo", "corregido_por", "fecha")
    list_filter = ("motivo",)
    list_select_related = ("asistencia__empleado", "corregido_por")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
