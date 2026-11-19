"""Consultas estadísticas reutilizadas por la vista de reportes y por el admin."""
from django.db.models import Count, Q

from .models import Cita, Medico, Paciente


def estadisticas():
    etiquetas = dict(Medico.Especialidad.choices)
    por_especialidad = [
        {"especialidad": etiquetas[f["medico__especialidad"]], "total": f["total"]}
        for f in Cita.objects.exclude(estado=Cita.Estado.CANCELADA)
        .values("medico__especialidad")
        .annotate(total=Count("id"))
        .order_by("-total")
    ]
    top_medicos = (
        Medico.objects.annotate(consultas=Count("citas", filter=Q(citas__estado=Cita.Estado.COMPLETADA)))
        .filter(consultas__gt=0)
        .order_by("-consultas", "apellidos")[:5]
    )
    pacientes_frecuentes = (
        Paciente.objects.annotate(num_citas=Count("citas", filter=~Q(citas__estado=Cita.Estado.CANCELADA)))
        .filter(num_citas__gt=0)
        .order_by("-num_citas", "apellidos")[:5]
    )
    total = Cita.objects.count()
    canceladas = Cita.objects.filter(estado=Cita.Estado.CANCELADA).count()
    return {
        "por_especialidad": por_especialidad,
        "top_medicos": top_medicos,
        "pacientes_frecuentes": pacientes_frecuentes,
        "total_citas": total,
        "tasa_cancelacion": round(canceladas * 100 / total, 1) if total else 0,
    }
