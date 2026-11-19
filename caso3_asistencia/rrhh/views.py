"""Vistas de la app rrhh.

La autorización jerárquica (permisos y alcance por área) viene de cuentas.permisos (Integrante 2).
"""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from cuentas.permisos import filtrar_por_alcance, permiso_requerido, puede_aprobar_permiso

from .forms import CorreccionAsistenciaForm, MarcacionForm, PermisoForm, RevisionPermisoForm
from .models import Area, Asistencia, Permiso
from .reportes import exportar_texto, resumen_por_empleado


def _empleado_o_403(request):
    empleado = getattr(request.user, "empleado", None)
    if empleado is None:
        raise PermissionDenied("Tu usuario no está vinculado a un empleado.")
    return empleado


@login_required
def panel(request):
    empleado = getattr(request.user, "empleado", None)
    contexto = {"empleado": empleado}
    if empleado:
        hoy = timezone.localdate()
        contexto["registros_hoy"] = empleado.asistencias.filter(fecha=hoy).order_by("hora_entrada")
        contexto["entrada_abierta"] = empleado.asistencias.filter(fecha=hoy, hora_salida__isnull=True).exists()
        contexto["mis_permisos"] = empleado.permisos.all()[:5]

        # Notificación de estado: permisos resueltos que el empleado aún no vio
        for p in empleado.permisos.filter(notificado=False):
            nivel = messages.SUCCESS if p.estado == Permiso.Estado.APROBADO else messages.ERROR
            texto = f"Tu permiso {p.get_tipo_display().lower()} del {p.fecha_inicio:%d/%m} al {p.fecha_fin:%d/%m} fue {p.get_estado_display().lower()}"
            if p.comentario_revision:
                texto += f": {p.comentario_revision}"
            messages.add_message(request, nivel, texto)
            p.notificado = True
            p.save(update_fields=["notificado"])

    if request.user.has_perm("rrhh.aprobar_permiso"):
        pendientes = filtrar_por_alcance(request.user, Permiso.objects.filter(estado=Permiso.Estado.PENDIENTE))
        contexto["pendientes_por_aprobar"] = pendientes.exclude(empleado__usuario=request.user).count()
    return render(request, "rrhh/panel.html", contexto)


@require_POST
@permiso_requerido("rrhh.registrar_asistencia")
def marcar_asistencia(request):
    empleado = _empleado_o_403(request)
    form = MarcacionForm(request.POST, empleado=empleado)
    if form.is_valid():
        registro = form.guardar()
        if form.cleaned_data["tipo"] == "entrada":
            messages.success(request, f"Entrada registrada a las {timezone.localtime(registro.hora_entrada):%H:%M}.")
        else:
            texto = f"Salida registrada a las {timezone.localtime(registro.hora_salida):%H:%M}. Trabajaste {registro.horas_trabajadas} horas"
            if registro.horas_extra:
                texto += f" ({registro.horas_extra} horas extra)"
            messages.success(request, texto + ".")
    else:
        messages.error(request, " ".join(form.non_field_errors()) or "Marcación inválida.")
    return redirect("panel")


@login_required
def mis_asistencias(request):
    empleado = _empleado_o_403(request)
    registros = empleado.asistencias.all()[:30]
    return render(request, "rrhh/mis_asistencias.html", {
        "registros": registros, "resumen": resumen_por_empleado(registros),
    })


@permiso_requerido("rrhh.solicitar_permiso")
def permiso_nuevo(request):
    empleado = _empleado_o_403(request)
    form = PermisoForm(request.POST or None, empleado=empleado)
    if request.method == "POST" and form.is_valid():
        permiso = form.save()
        messages.success(request, f"Solicitud enviada: {permiso}. Estado: pendiente de aprobación.")
        return redirect("mis_permisos")
    return render(request, "rrhh/permiso_form.html", {"form": form, "empleado": empleado})


@login_required
def mis_permisos(request):
    empleado = _empleado_o_403(request)
    return render(request, "rrhh/mis_permisos.html", {
        "permisos": empleado.permisos.select_related("revisado_por"),
        "empleado": empleado,
    })


@permiso_requerido("rrhh.aprobar_permiso")
def permisos_pendientes(request):
    permisos = filtrar_por_alcance(
        request.user,
        Permiso.objects.select_related("empleado__area").filter(estado=Permiso.Estado.PENDIENTE),
    ).exclude(empleado__usuario=request.user)
    return render(request, "rrhh/permisos_pendientes.html", {"permisos": permisos})


@permiso_requerido("rrhh.aprobar_permiso")
def permiso_revisar(request, pk):
    permiso = get_object_or_404(
        Permiso.objects.select_related("empleado__area"), pk=pk, estado=Permiso.Estado.PENDIENTE
    )
    if not puede_aprobar_permiso(request.user, permiso):
        raise PermissionDenied("Solo el jefe del área del empleado o RRHH pueden revisar este permiso.")
    form = RevisionPermisoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        aprobar = form.cleaned_data["decision"] == "aprobar"
        if aprobar and permiso.tipo == Permiso.Tipo.VACACIONES and permiso.dias > permiso.empleado.dias_vacaciones_disponibles:
            messages.error(request, f"{permiso.empleado} ya no tiene días de vacaciones suficientes.")
        else:
            permiso.resolver(aprobar, request.user, form.cleaned_data["comentario"])
            messages.success(request, f"Permiso {permiso.get_estado_display().lower()}. Se notificará a {permiso.empleado.nombres}.")
            return redirect("permisos_pendientes")
    return render(request, "rrhh/permiso_revisar.html", {"form": form, "permiso": permiso})


@permiso_requerido("rrhh.corregir_asistencia")
def asistencia_corregir(request, pk):
    asistencia = get_object_or_404(Asistencia.objects.select_related("empleado__area"), pk=pk)
    form = CorreccionAsistenciaForm(request.POST or None, asistencia=asistencia)
    if request.method == "POST" and form.is_valid():
        form.save(usuario=request.user)
        messages.success(request, f"Registro de {asistencia.empleado} del {asistencia.fecha:%d/%m/%Y} corregido.")
        return redirect("reporte_asistencia")
    return render(request, "rrhh/asistencia_corregir.html", {"form": form, "asistencia": asistencia})


@permiso_requerido("rrhh.ver_reportes_area", "rrhh.ver_reportes_globales", cualquiera=True)
def reporte_asistencia(request):
    """Jefes: solo su área. Admin RRHH y Contador: toda la empresa."""
    hoy = timezone.localdate()
    try:
        anio, mes = map(int, request.GET.get("mes", f"{hoy:%Y-%m}").split("-"))
        inicio = date(anio, mes, 1)
    except ValueError:
        inicio = hoy.replace(day=1)
    fin = date(inicio.year + inicio.month // 12, inicio.month % 12 + 1, 1)

    registros = filtrar_por_alcance(
        request.user,
        Asistencia.objects.select_related("empleado__area").filter(fecha__gte=inicio, fecha__lt=fin),
    )
    area = request.GET.get("area", "")
    if area:
        registros = registros.filter(empleado__area_id=area)
    registros = registros.order_by("empleado__apellidos", "-fecha")

    if request.GET.get("formato") == "txt":
        texto = exportar_texto(registros, f"REPORTE DE ASISTENCIA {inicio:%m/%Y} - TecnoAndes S.A.C.")
        respuesta = HttpResponse(texto, content_type="text/plain; charset=utf-8")
        respuesta["Content-Disposition"] = f'attachment; filename="asistencia_{inicio:%Y_%m}.txt"'
        return respuesta

    return render(request, "rrhh/reporte_asistencia.html", {
        "resumen": resumen_por_empleado(registros),
        "registros": registros[:60],
        "mes": f"{inicio:%Y-%m}",
        "areas": Area.objects.all(),
        "area": area,
        "global": request.user.has_perm("rrhh.ver_reportes_globales"),
    })
