"""Vistas de la app consultas.

La autorización (permisos y reglas de propiedad) viene de cuentas.permisos (Integrante 2).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from cuentas.permisos import permiso_requerido, puede_cancelar_cita, puede_ver_historial

from .estadisticas import estadisticas
from .forms import CancelacionForm, CitaForm, ConsultaForm, NotaForm, PacienteForm
from .models import Cita, Consulta, Medico, NotaConsulta, Paciente


def _citas():
    return Cita.objects.select_related("paciente", "medico")


@login_required
def panel(request):
    """Inicio según el tipo de usuario."""
    ahora = timezone.now()
    hoy = timezone.localdate()
    paciente = getattr(request.user, "paciente", None)
    medico = getattr(request.user, "medico", None)

    if paciente:
        contexto = {
            "tipo": "paciente", "paciente": paciente,
            "citas": _citas().filter(paciente=paciente, estado=Cita.Estado.PENDIENTE, fecha_hora__gte=ahora)[:5],
        }
    elif medico:
        contexto = {
            "tipo": "medico", "medico": medico,
            "citas": _citas().filter(medico=medico, fecha_hora__date=hoy).exclude(estado=Cita.Estado.CANCELADA),
        }
    else:
        contexto = {
            "tipo": "general",
            "citas": _citas().filter(fecha_hora__date=hoy).exclude(estado=Cita.Estado.CANCELADA),
        }
    contexto["hoy"] = hoy
    return render(request, "consultas/panel.html", contexto)


@login_required
def cita_lista(request):
    """Pacientes y médicos ven sus citas; recepción y admin ven todas."""
    citas = _citas()
    paciente = getattr(request.user, "paciente", None)
    medico = getattr(request.user, "medico", None)
    if paciente:
        citas = citas.filter(paciente=paciente)
    elif medico:
        citas = citas.filter(medico=medico)
    elif not request.user.has_perm("consultas.view_cita"):
        raise PermissionDenied("No tiene permiso para ver la agenda.")

    filtro = request.GET.get("estado", "pendiente")
    if filtro in Cita.Estado.values:
        citas = citas.filter(estado=filtro)
    if filtro == "pendiente":
        citas = citas.filter(fecha_hora__gte=timezone.now() - timezone.timedelta(hours=12))
    return render(request, "consultas/citas_lista.html", {
        "citas": citas, "filtro": filtro, "estados": Cita.Estado.choices,
    })


@permiso_requerido("consultas.agendar_cita")
def cita_nueva(request):
    especialidad = request.GET.get("especialidad", "")
    form = CitaForm(request.POST or None, usuario=request.user, especialidad=especialidad)
    if request.method == "POST" and form.is_valid():
        cita = form.save()
        messages.success(
            request,
            f"Cita agendada para {cita.paciente.nombre_completo} con Dr(a). {cita.medico.apellidos} "
            f"el {timezone.localtime(cita.fecha_hora):%d/%m/%Y a las %H:%M}.",
        )
        return redirect("cita_lista")
    return render(request, "consultas/cita_form.html", {
        "form": form,
        "especialidades": Medico.Especialidad.choices,
        "especialidad": especialidad,
    })


@permiso_requerido("consultas.cancelar_cita")
def cita_cancelar(request, pk):
    cita = get_object_or_404(_citas(), pk=pk, estado=Cita.Estado.PENDIENTE)
    if not puede_cancelar_cita(request.user, cita):
        raise PermissionDenied("Solo puede cancelar sus propias citas.")
    form = CancelacionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cita.estado = Cita.Estado.CANCELADA
        cita.motivo_cancelacion = form.cleaned_data["motivo"]
        cita.save(update_fields=["estado", "motivo_cancelacion"])
        messages.info(request, f"La cita del {timezone.localtime(cita.fecha_hora):%d/%m/%Y %H:%M} fue cancelada.")
        return redirect("cita_lista")
    return render(request, "consultas/cita_cancelar.html", {"form": form, "cita": cita})


@permiso_requerido("consultas.add_consulta")
def consulta_registrar(request, pk):
    """El médico registra la atención. Después la consulta ya no se puede editar."""
    cita = get_object_or_404(_citas(), pk=pk, estado=Cita.Estado.PENDIENTE)
    medico = getattr(request.user, "medico", None)
    if medico and cita.medico_id != medico.pk:
        raise PermissionDenied("Solo el médico asignado puede registrar esta consulta.")
    form = ConsultaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            consulta = form.save(commit=False)
            consulta.cita = cita
            consulta.registrada_por = request.user
            consulta.save()
            cita.estado = Cita.Estado.COMPLETADA
            cita.save(update_fields=["estado"])
        messages.success(request, "Consulta registrada en el historial clínico.")
        return redirect("historial_paciente", pk=cita.paciente_id)
    return render(request, "consultas/consulta_form.html", {"form": form, "cita": cita})


@login_required
def historial(request, pk):
    """Historial clínico: solo médicos y el propio paciente (lo audita el middleware)."""
    paciente = get_object_or_404(Paciente, pk=pk)
    if not puede_ver_historial(request.user, paciente):
        raise PermissionDenied("El historial clínico solo lo pueden ver los médicos y el propio paciente.")
    consultas = (
        Consulta.objects.filter(cita__paciente=paciente)
        .select_related("cita__medico", "registrada_por")
        .prefetch_related("notas__autor")
    )
    return render(request, "consultas/historial.html", {
        "paciente": paciente,
        "consultas": consultas,
        "nota_form": NotaForm() if request.user.has_perm("consultas.add_notaconsulta") else None,
    })


@require_POST
@permiso_requerido("consultas.add_notaconsulta")
def nota_agregar(request, pk):
    consulta = get_object_or_404(Consulta.objects.select_related("cita__paciente"), pk=pk)
    paciente = consulta.cita.paciente
    if not puede_ver_historial(request.user, paciente):
        raise PermissionDenied("No puede agregar notas a este historial.")
    form = NotaForm(request.POST)
    if form.is_valid():
        NotaConsulta.objects.create(consulta=consulta, texto=form.cleaned_data["texto"], autor=request.user)
        messages.success(request, "Nota agregada a la consulta.")
    else:
        messages.error(request, " ".join(form.errors["texto"]))
    return redirect("historial_paciente", pk=paciente.pk)


@permiso_requerido("consultas.add_paciente")
def paciente_nuevo(request):
    form = PacienteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        paciente = form.save()
        messages.success(request, f"Paciente {paciente.nombre_completo} registrado.")
        return redirect("panel")
    return render(request, "consultas/paciente_form.html", {"form": form})


@permiso_requerido("consultas.generar_reportes")
def reportes(request):
    return render(request, "consultas/reportes.html", estadisticas())
