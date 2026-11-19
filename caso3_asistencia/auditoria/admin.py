"""Los logs de auditoría solo los ven los administradores (solo lectura y sin borrado)."""
from django.contrib import admin
from django.utils.html import format_html

from cuentas.roles import ADMIN_RRHH as ADMIN

from .models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "nombre_usuario", "ip", "accion", "metodo", "ruta", "nivel_visual")
    list_filter = ("nivel", "accion", "fecha")
    search_fields = ("nombre_usuario", "accion", "ruta", "ip")
    date_hierarchy = "fecha"
    list_per_page = 30

    @admin.display(description="Nivel", ordering="nivel")
    def nivel_visual(self, obj):
        color = "#dc3545" if obj.nivel == "WARNING" else "#0d6efd"
        return format_html('<strong style="color:{};">{}</strong>', color, obj.nivel)

    def _es_admin(self, request):
        return request.user.is_superuser or request.user.groups.filter(name=ADMIN).exists()

    def has_view_permission(self, request, obj=None):
        return self._es_admin(request)

    def has_module_permission(self, request):
        return self._es_admin(request)

    # Los registros no se crean, editan ni borran a mano
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
