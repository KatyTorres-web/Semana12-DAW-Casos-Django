"""Cálculo del reporte de asistencia (reutilizado por la vista y por el admin)."""
from collections import OrderedDict
from decimal import Decimal


def resumen_por_empleado(asistencias):
    """Agrupa registros por empleado: días, horas trabajadas y horas extra."""
    filas = OrderedDict()
    for a in asistencias:
        fila = filas.setdefault(a.empleado_id, {
            "empleado": a.empleado, "dias": 0, "horas": Decimal("0"), "extra": Decimal("0"), "sin_salida": 0,
        })
        fila["dias"] += 1
        if a.horas_trabajadas is None:
            fila["sin_salida"] += 1
        else:
            fila["horas"] += a.horas_trabajadas
            fila["extra"] += a.horas_extra
    return list(filas.values())


def exportar_texto(asistencias, titulo="REPORTE DE ASISTENCIA"):
    """Exportación simulada: genera un texto plano tabulado para planilla."""
    lineas = [titulo, "=" * 78, f"{'DNI':<10}{'Empleado':<32}{'Área':<14}{'Días':>5}{'Horas':>9}{'Extra':>8}", "-" * 78]
    for f in resumen_por_empleado(asistencias):
        e = f["empleado"]
        lineas.append(f"{e.dni:<10}{e.nombre_completo[:31]:<32}{e.area.nombre[:13]:<14}{f['dias']:>5}{f['horas']:>9}{f['extra']:>8}")
    lineas.append("-" * 78)
    return "\n".join(lineas) + "\n"
