"""Datos de prueba: 5 áreas, 11 empleados (1 desactivado), 50 asistencias y 10 permisos.

Uso: python manage.py poblar_datos   (se puede repetir, no duplica)
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone

from cuentas.roles import ADMIN_RRHH, CONTADOR, EMPLEADO, JEFE_AREA
from rrhh.models import Area, Asistencia, Empleado, Permiso

PASSWORD = "Tecno2026!"
AREAS = ["Sistemas", "Contabilidad", "Ventas", "Logística", "RRHH"]

# usuario, nombres, apellidos, DNI, cargo, área, ingreso, contrato, salario, entrada, salida (jornada de 8 h), rol, activo
EMPLEADOS = [
    ("srios", "Sandra", "Ríos Mendoza", "41234501", "Gerente de RRHH", "RRHH", date(2015, 3, 2), "planilla", "6500", 8, 16, ADMIN_RRHH, True),
    ("jvilca", "Jorge", "Vilca Soto", "42345602", "Jefe de Sistemas", "Sistemas", date(2017, 8, 14), "planilla", "6000", 8, 16, JEFE_AREA, True),
    ("aparedes", "Ana", "Paredes Luna", "43456703", "Desarrolladora web", "Sistemas", date(2021, 1, 11), "planilla", "4200", 9, 17, EMPLEADO, True),
    ("mtorres", "Miguel", "Torres Arana", "44567804", "Soporte TI", "Sistemas", date(2023, 6, 5), "locacion", "2800", 8, 16, EMPLEADO, True),
    ("cramirez", "Carla", "Ramírez Poma", "45678905", "Jefa de Ventas", "Ventas", date(2018, 2, 19), "planilla", "5500", 9, 17, JEFE_AREA, True),
    ("lhuaman", "Luis", "Huamán Quispe", "46789006", "Ejecutivo de ventas", "Ventas", date(2022, 9, 1), "planilla", "3000", 9, 17, EMPLEADO, True),
    ("rcondor", "Rosa", "Cóndor Lima", "47890107", "Contadora", "Contabilidad", date(2016, 5, 23), "planilla", "5000", 8, 16, CONTADOR, True),
    ("ebaldeon", "Elmer", "Baldeón Ríos", "48901208", "Asistente contable", "Contabilidad", date(2024, 3, 4), "planilla", "2500", 8, 16, EMPLEADO, True),
    ("pyupanqui", "Pilar", "Yupanqui Salas", "49012309", "Jefa de Logística", "Logística", date(2019, 10, 7), "planilla", "5200", 7, 15, JEFE_AREA, True),
    ("fcanchari", "Frank", "Canchari Vega", "40123410", "Almacenero", "Logística", date(2023, 11, 20), "locacion", "2200", 7, 15, EMPLEADO, True),
    ("imucha", "Iván", "Mucha Rojas", "40234511", "Practicante", "Sistemas", date(2025, 4, 1), "locacion", "1100", 8, 16, EMPLEADO, False),
]

# usuario, tipo, días desde hoy (inicio), duración, estado, motivo
PERMISOS = [
    ("lhuaman", "vacaciones", -40, 10, "aprobado", "Vacaciones programadas para viaje familiar a Cusco"),
    ("aparedes", "medico", -15, 2, "aprobado", "Descanso médico por cuadro de gripe con fiebre alta"),
    ("mtorres", "personal", 6, 1, "pendiente", "Trámite personal en el Registro Nacional de Identificación"),
    ("ebaldeon", "duelo", -25, 3, "aprobado", "Fallecimiento de familiar directo en la ciudad de Jauja"),
    ("fcanchari", "vacaciones", 10, 5, "pendiente", "Vacaciones para atender asuntos familiares en Huancayo"),
    ("lhuaman", "personal", -10, 1, "rechazado", "Asistencia a evento deportivo de la empresa de un amigo"),
    ("aparedes", "vacaciones", 20, 7, "pendiente", "Vacaciones de fin de año con la familia en la costa"),
    ("jvilca", "vacaciones", 14, 5, "pendiente", "Descanso vacacional programado desde inicio de año"),
    ("rcondor", "personal", -5, 2, "aprobado", "Mudanza de domicilio dentro de la provincia de Huancayo"),
    ("cramirez", "otro", 8, 1, "pendiente", "Capacitación externa sobre técnicas de ventas consultivas"),
]


def dias_habiles_anteriores(hoy, cantidad):
    dias, d = [], hoy
    while len(dias) < cantidad:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            dias.append(d)
    return sorted(dias)


class Command(BaseCommand):
    help = "Carga áreas, empleados, asistencias y permisos de prueba"

    def handle(self, *args, **options):
        User = get_user_model()
        areas = {n: Area.objects.get_or_create(nombre=n)[0] for n in AREAS}

        empleados = {}
        for (username, nom, ape, dni, cargo, area, ingreso, contrato, salario,
             h_in, h_out, rol, activo) in EMPLEADOS:
            user, creado = User.objects.get_or_create(
                username=username,
                defaults={"first_name": nom, "last_name": ape, "email": f"{username}@tecnoandes.pe"},
            )
            if creado:
                user.set_password(PASSWORD)
                user.save()
            user.groups.set([Group.objects.get_or_create(name=rol)[0]])
            emp, _ = Empleado.objects.update_or_create(
                dni=dni,
                defaults={
                    "usuario": user, "nombres": nom, "apellidos": ape, "cargo": cargo,
                    "area": areas[area], "fecha_ingreso": ingreso, "tipo_contrato": contrato,
                    "email": f"{username}@tecnoandes.pe", "salario": Decimal(salario),
                    "hora_entrada": time(h_in), "hora_salida": time(h_out), "activo": activo,
                },
            )
            empleados[username] = emp
            if rol == JEFE_AREA or rol == ADMIN_RRHH:
                areas[area].jefe = emp
                areas[area].save(update_fields=["jefe"])

        if Asistencia.objects.exists():
            self.stdout.write("Las asistencias ya existían: no se crean de nuevo.")
        else:
            self._crear_asistencias([e for e in empleados.values() if e.activo])

        if not Permiso.objects.exists():
            hoy = timezone.localdate()
            revisor = empleados["srios"].usuario
            for username, tipo, desde, duracion, estado, motivo in PERMISOS:
                inicio = hoy + timedelta(days=desde)
                Permiso.objects.create(
                    empleado=empleados[username], tipo=tipo, fecha_inicio=inicio,
                    fecha_fin=inicio + timedelta(days=duracion - 1), motivo=motivo, estado=estado,
                    documento_adjunto="Certificado médico N.° 4512" if tipo == "medico" else "",
                    revisado_por=revisor if estado != "pendiente" else None,
                    fecha_revision=timezone.now() if estado != "pendiente" else None,
                    comentario_revision="No corresponde a un motivo laboral" if estado == "rechazado" else "",
                )

        self.stdout.write(self.style.SUCCESS(
            f"[OK] {Area.objects.count()} áreas, {Empleado.objects.count()} empleados, "
            f"{Asistencia.objects.count()} asistencias, {Permiso.objects.count()} permisos "
            f"(contraseña: {PASSWORD})"
        ))

    def _crear_asistencias(self, empleados):
        tz = timezone.get_current_timezone()
        dias = dias_habiles_anteriores(timezone.localdate(), 5)
        for i, emp in enumerate(empleados):
            for j, dia in enumerate(dias):
                tardanza = (i * 7 + j * 3) % 15 - 5                 # entre 5 min antes y 9 min tarde
                extra = 90 if (i + j) % 4 == 0 else (i * 11 + j * 5) % 20   # algunos días con horas extra
                entrada = datetime.combine(dia, emp.hora_entrada) + timedelta(minutes=tardanza)
                salida = datetime.combine(dia, emp.hora_salida) + timedelta(minutes=extra)
                Asistencia.objects.create(
                    empleado=emp, fecha=dia,
                    hora_entrada=timezone.make_aware(entrada, tz),
                    hora_salida=timezone.make_aware(salida, tz),
                )
