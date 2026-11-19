"""Vistas de la app prestamos.

La autorización por rol viene de cuentas.permisos (Integrante 2).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from cuentas.permisos import rol_requerido
from cuentas.roles import ADMIN, ASISTENTE, DOCENTE

from .forms import DevolucionForm, PrestamoForm
from .models import Equipo, Laboratorio, Prestamo


def catalogo(request):
    """Catálogo público (también para invitados)."""
    # Con anotaciones (GROUP BY) Django ignora Meta.ordering: se ordena explícitamente
    equipos = (
        Equipo.objects.select_related("laboratorio")
        .con_disponibilidad()
        .order_by("codigo_patrimonial")
    )

    q = request.GET.get("q", "").strip()
    laboratorio = request.GET.get("laboratorio", "")
    estado = request.GET.get("estado", "")
    if q:
        equipos = equipos.filter(
            Q(codigo_patrimonial__icontains=q) | Q(nombre__icontains=q) | Q(categoria__icontains=q)
        )
    if laboratorio:
        equipos = equipos.filter(laboratorio_id=laboratorio)
    if estado:
        equipos = equipos.filter(estado=estado)

    return render(request, "prestamos/catalogo.html", {
        "equipos": equipos,
        "laboratorios": Laboratorio.objects.all(),
        "estados": Equipo.Estado.choices,
        "filtros": {"q": q, "laboratorio": laboratorio, "estado": estado},
    })


@login_required
def prestamo_lista(request):
    """Docentes: solo sus préstamos. Asistentes y admin: todos."""
    prestamos = Prestamo.objects.select_related("docente", "equipo", "equipo__laboratorio")
    puede_ver_todos = request.user.has_perm("prestamos.ver_todos_los_prestamos")
    if not puede_ver_todos:
        prestamos = prestamos.filter(docente=request.user)

    filtro = request.GET.get("estado", "activos")
    hoy = timezone.localdate()
    if filtro == "activos":
        prestamos = prestamos.filter(estado=Prestamo.Estado.ACTIVO)
    elif filtro == "vencidos":
        prestamos = prestamos.filter(
            estado=Prestamo.Estado.ACTIVO, fecha_devolucion_prevista__lt=hoy
        )
    elif filtro == "devueltos":
        prestamos = prestamos.filter(estado=Prestamo.Estado.DEVUELTO)

    return render(request, "prestamos/lista.html", {
        "prestamos": prestamos,
        "filtro": filtro,
        "puede_ver_todos": puede_ver_todos,
    })


@rol_requerido(ADMIN, DOCENTE, ASISTENTE)
def prestamo_nuevo(request):
    form = PrestamoForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        prestamo = form.save()
        messages.success(
            request,
            f"Préstamo #{prestamo.pk} registrado: {prestamo.cantidad} x {prestamo.equipo.nombre} "
            f"para {prestamo.docente.get_full_name() or prestamo.docente.username}, "
            f"devolver el {prestamo.fecha_devolucion_prevista:%d/%m/%Y}.",
        )
        return redirect("prestamo_lista")
    return render(request, "prestamos/form_prestamo.html", {"form": form})


@rol_requerido(ASISTENTE)
def prestamo_devolver(request, pk):
    """Solo asistentes registran devoluciones."""
    prestamo = get_object_or_404(
        Prestamo.objects.select_related("docente", "equipo", "equipo__laboratorio"),
        pk=pk, estado=Prestamo.Estado.ACTIVO,
    )
    form = DevolucionForm(request.POST or None, prestamo=prestamo)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            prestamo.registrar_devolucion(
                fecha=form.cleaned_data["fecha_devolucion"],
                estado_retorno=form.cleaned_data["estado_retorno"],
                observaciones=form.cleaned_data["observaciones"],
                usuario=request.user,
            )
        messages.success(request, f"Devolución del préstamo #{prestamo.pk} registrada.")
        return redirect("prestamo_lista")
    return render(request, "prestamos/form_devolucion.html", {"form": form, "prestamo": prestamo})


@rol_requerido(ADMIN)
def equipo_eliminar(request, pk):
    """Solo el administrador elimina equipos."""
    equipo = get_object_or_404(Equipo.objects.select_related("laboratorio"), pk=pk)
    if request.method == "POST":
        try:
            equipo.delete()
            messages.success(request, f"Equipo {equipo.codigo_patrimonial} eliminado.")
        except ProtectedError:
            messages.error(
                request,
                f"No se puede eliminar {equipo.codigo_patrimonial} porque tiene préstamos "
                'registrados. Márquelo como "Dado de baja".',
            )
        return redirect("catalogo")
    return render(request, "prestamos/confirmar_eliminar.html", {"equipo": equipo})
