"""Django Admin para la gestión operativa del Centro Médico."""
from django.contrib import admin, messages
from django.db.models import Count, Max, Q
from django.utils import timezone
from django.utils.html import format_html

from .estadisticas import estadisticas
from .forms import MedicoForm, PacienteForm
from .models import Cita, Consulta, Medico, NotaConsulta, Paciente

COLORES = {"pendiente": "#0d6efd", "completada": "#198754", "cancelada": "#6c757d"}


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    form = PacienteForm
    list_display = ("dni", "nombre", "tipo", "codigo_uncp", "edad_col", "citas_totales", "dias_ultima_consulta")
    list_filter = ("tipo",)
    search_fields = ("dni", "nombres", "apellidos", "codigo_uncp")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            num_citas=Count("citas", filter=~Q(citas__estado=Cita.Estado.CANCELADA), distinct=True),
            ultima_consulta=Max("citas__consulta__creado_en"),
        )

    @admin.display(description="Paciente", ordering="apellidos")
    def nombre(self, obj):
        return f"{obj.apellidos}, {obj.nombres}"

    @admin.display(description="Edad", ordering="-fecha_nacimiento")
    def edad_col(self, obj):
        return f"{obj.edad} años"

    @admin.display(description="Citas", ordering="num_citas")
    def citas_totales(self, obj):
        return obj.num_citas

    @admin.display(description="Días desde última consulta", ordering="ultima_consulta")
    def dias_ultima_consulta(self, obj):
        if not obj.ultima_consulta:
            return "Sin consultas"
        return f"{(timezone.now() - obj.ultima_consulta).days} días"


@admin.register(Medico)
class MedicoAdmin(admin.ModelAdmin):
    form = MedicoForm
    list_display = ("cmp", "nombre", "especialidad", "consultorio", "horario", "consultas_realizadas", "citas_pendientes")
    list_filter = ("especialidad",)
    search_fields = ("cmp", "nombres", "apellidos")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            completadas=Count("citas", filter=Q(citas__estado=Cita.Estado.COMPLETADA)),
            pendientes=Count("citas", filter=Q(citas__estado=Cita.Estado.PENDIENTE)),
        )

    @admin.display(description="Médico", ordering="apellidos")
    def nombre(self, obj):
        return f"Dr(a). {obj.nombres} {obj.apellidos}"

    @admin.display(description="Consultas realizadas", ordering="completadas")
    def consultas_realizadas(self, obj):
        return obj.completadas

    @admin.display(description="Citas pendientes", ordering="pendientes")
    def citas_pendientes(self, obj):
        return obj.pendientes


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    """Agenda diaria: filtrar por 'Hoy' y por médico."""

    change_list_template = "admin/consultas/cita/change_list.html"
    list_display = ("hora", "medico_nombre", "especialidad", "paciente_nombre", "estado_visual", "motivo_corto")
    list_filter = ("fecha_hora", "medico", "medico__especialidad", "estado")
    search_fields = ("paciente__dni", "paciente__nombres", "paciente__apellidos", "medico__apellidos")
    date_hierarchy = "fecha_hora"
    list_select_related = ("paciente", "medico")
    ordering = ("fecha_hora",)
    actions = ["marcar_completadas"]

    @admin.display(description="Fecha y hora", ordering="fecha_hora")
    def hora(self, obj):
        return timezone.localtime(obj.fecha_hora).strftime("%d/%m/%Y %H:%M")

    @admin.display(description="Médico", ordering="medico__apellidos")
    def medico_nombre(self, obj):
        return f"Dr(a). {obj.medico.apellidos}"

    @admin.display(description="Especialidad", ordering="medico__especialidad")
    def especialidad(self, obj):
        return obj.medico.get_especialidad_display()

    @admin.display(description="Paciente", ordering="paciente__apellidos")
    def paciente_nombre(self, obj):
        return f"{obj.paciente.apellidos}, {obj.paciente.nombres}"

    @admin.display(description="Estado", ordering="estado")
    def estado_visual(self, obj):
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:12px;">{}</span>',
            COLORES[obj.estado], obj.get_estado_display(),
        )

    @admin.display(description="Motivo")
    def motivo_corto(self, obj):
        return obj.motivo[:50] + ("..." if len(obj.motivo) > 50 else "")

    @admin.action(description="Marcar citas como completadas")
    def marcar_completadas(self, request, queryset):
        total = queryset.filter(estado=Cita.Estado.PENDIENTE).update(estado=Cita.Estado.COMPLETADA)
        self.message_user(request, f"{total} cita(s) marcadas como completadas.", messages.SUCCESS)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["estadisticas"] = estadisticas()
        return super().changelist_view(request, extra_context=extra_context)


class NotaInline(admin.TabularInline):
    model = NotaConsulta
    extra = 0
    readonly_fields = ("texto", "autor", "creado_en")
    can_delete = False


@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    """Integridad: las consultas registradas son de solo lectura."""

    list_display = ("cita", "medico", "diagnostico_corto", "proxima_cita", "creado_en")
    list_select_related = ("cita__paciente", "cita__medico")
    search_fields = ("cita__paciente__dni", "cita__paciente__apellidos", "diagnostico")
    inlines = [NotaInline]

    @admin.display(description="Médico")
    def medico(self, obj):
        return obj.cita.medico

    @admin.display(description="Diagnóstico")
    def diagnostico_corto(self, obj):
        return obj.diagnostico[:60]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
