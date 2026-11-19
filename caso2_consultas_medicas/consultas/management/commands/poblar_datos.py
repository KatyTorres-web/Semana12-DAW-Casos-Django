"""Datos de prueba: 8 médicos, 15 pacientes, 30 citas y 16 consultas.

Uso: python manage.py poblar_datos   (se puede repetir, no duplica)
"""
import unicodedata
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone

from consultas.models import Cita, Consulta, Medico, Paciente
from cuentas.roles import MEDICO, PACIENTE

PASSWORD = "Uncp2026!"
MANANA = (time(8, 0), time(13, 0))
TARDE = (time(13, 0), time(18, 0))

# usuario, nombres, apellidos, CMP, especialidad, consultorio, turno
MEDICOS = [
    ("lrojas", "Luis", "Rojas Paredes", "45123", "medicina_general", "C-101", MANANA),
    ("acastro", "Ana", "Castro Vílchez", "51234", "medicina_general", "C-102", TARDE),
    ("jsalazar", "Jorge", "Salazar Ñaupari", "38456", "odontologia", "C-201", MANANA),
    ("pmeza", "Patricia", "Meza Canchanya", "62345", "psicologia", "C-202", TARDE),
    ("rlopez", "Raúl", "López Inga", "47890", "nutricion", "C-203", MANANA),
    ("cflores", "Carmen", "Flores Huaynalaya", "55678", "obstetricia", "C-301", MANANA),
    ("evega", "Eduardo", "Vega Porras", "123456", "oftalmologia", "C-302", TARDE),
    ("mguzman", "Mónica", "Guzmán Ricse", "49012", "medicina_general", "C-103", MANANA),
]

# DNI, nombres, apellidos, nacimiento, tipo, código UNCP, alergias  (los 5 primeros tienen usuario)
PACIENTES = [
    ("71234567", "Diego", "Arana Quispe", date(2003, 5, 14), "estudiante", "2021100101", "Penicilina"),
    ("72345678", "Valeria", "Bendezú Ríos", date(2002, 9, 2), "estudiante", "2020100215", ""),
    ("73456789", "Kevin", "Cárdenas Soto", date(2004, 1, 20), "estudiante", "2022100322", ""),
    ("74567890", "Lucero", "Dávila Huamán", date(2001, 11, 8), "estudiante", "2019100430", "Mariscos"),
    ("40123456", "Hugo", "Espinoza Laura", date(1975, 3, 30), "docente", "D0451", ""),
    ("75678901", "Fiorella", "Gálvez Mucha", date(2003, 7, 25), "estudiante", "2021100540", ""),
    ("76789012", "Renzo", "Huamán Pari", date(2002, 2, 11), "estudiante", "2020100655", "Ibuprofeno"),
    ("77890123", "Melissa", "Inga Rojas", date(2004, 6, 3), "estudiante", "2022100760", ""),
    ("41234567", "Silvia", "Janampa Torres", date(1980, 12, 19), "docente", "D0522", ""),
    ("78901234", "Brayan", "Lazo Coronel", date(2003, 4, 9), "estudiante", "2021100877", ""),
    ("79012345", "Noelia", "Mallma Yauri", date(2001, 8, 27), "estudiante", "2019100988", "Látex"),
    ("70123456", "Óscar", "Navarro Quinto", date(2002, 10, 15), "estudiante", "2020101034", ""),
    ("42345678", "Teresa", "Orihuela Baldeón", date(1968, 1, 5), "docente", "D0610", "Aspirina"),
    ("70234567", "Piero", "Paucar Limaylla", date(2004, 9, 30), "estudiante", "2022101150", ""),
    ("70345678", "Rocío", "Quispe Chávez", date(2003, 12, 12), "estudiante", "2021101266", ""),
]

DIAGNOSTICOS = {
    "medicina_general": ("Faringitis aguda de origen viral", "Reposo e hidratación", "Paracetamol 500 mg c/8 h por 3 días"),
    "odontologia": ("Caries dental en pieza 36", "Curación con resina", ""),
    "psicologia": ("Ansiedad leve asociada a periodo de exámenes", "Terapia cognitivo-conductual, 4 sesiones", ""),
    "nutricion": ("Sobrepeso grado I, IMC 27", "Plan alimentario hipocalórico", ""),
    "obstetricia": ("Control preventivo sin hallazgos", "Control anual", "Ácido fólico 1 mg diario"),
    "oftalmologia": ("Miopía leve en ambos ojos", "Uso de lentes correctivos", "Lágrimas artificiales"),
}


def sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def dia_habil(base, desplazamiento):
    """Fecha a N días de 'base', movida a un día de semana (lunes a viernes)."""
    d = base + timedelta(days=desplazamiento)
    while d.weekday() >= 5:
        d += timedelta(days=-1 if desplazamiento < 0 else 1)
    return d


class Command(BaseCommand):
    help = "Carga médicos, pacientes, citas y consultas de prueba"

    def handle(self, *args, **options):
        User = get_user_model()
        grupo_medico, _ = Group.objects.get_or_create(name=MEDICO)
        grupo_paciente, _ = Group.objects.get_or_create(name=PACIENTE)

        def usuario(username, nombres, apellidos, grupo):
            user, creado = User.objects.get_or_create(
                username=username,
                defaults={"first_name": nombres, "last_name": apellidos, "email": f"{username}@uncp.edu.pe"},
            )
            if creado:
                user.set_password(PASSWORD)
                user.save()
            user.groups.add(grupo)
            return user

        medicos = []
        for username, nombres, apellidos, cmp, esp, consultorio, (inicio, fin) in MEDICOS:
            medico, _ = Medico.objects.update_or_create(
                cmp=cmp,
                defaults={
                    "usuario": usuario(username, nombres, apellidos, grupo_medico),
                    "nombres": nombres, "apellidos": apellidos, "especialidad": esp,
                    "consultorio": consultorio, "hora_inicio": inicio, "hora_fin": fin,
                },
            )
            medicos.append(medico)

        pacientes = []
        for i, (dni, nombres, apellidos, nac, tipo, codigo, alergias) in enumerate(PACIENTES):
            username = sin_tildes(f"{nombres[0]}{apellidos.split()[0]}".lower())
            paciente, _ = Paciente.objects.update_or_create(
                dni=dni,
                defaults={
                    "nombres": nombres, "apellidos": apellidos, "fecha_nacimiento": nac,
                    "tipo": tipo, "codigo_uncp": codigo, "email": f"{username}@uncp.edu.pe",
                    "alergias": alergias,
                    "usuario": usuario(username, nombres, apellidos, grupo_paciente) if i < 5 else None,
                },
            )
            pacientes.append(paciente)

        if Cita.objects.exists():
            self.stdout.write("Las citas ya existían: no se crean de nuevo.")
        else:
            self._crear_citas(medicos, pacientes)

        self.stdout.write(self.style.SUCCESS(
            f"[OK] {Medico.objects.count()} médicos, {Paciente.objects.count()} pacientes, "
            f"{Cita.objects.count()} citas, {Consulta.objects.count()} consultas "
            f"(contraseña: {PASSWORD})"
        ))

    def _crear_citas(self, medicos, pacientes):
        hoy = timezone.localdate()
        tz = timezone.get_current_timezone()
        dias = [dia_habil(hoy, d) for d in (-12, -8, -5, -2)] + [hoy, dia_habil(hoy, 2)]
        for n, dia in enumerate(dias):
            for k in range(5):
                medico = medicos[(n * 3 + k) % 8]
                paciente = pacientes[(n * 5 + k) % 15]
                inicio = datetime.combine(dia, medico.hora_inicio) + timedelta(hours=1 + k % 3)
                if dia < hoy:
                    estado = Cita.Estado.CANCELADA if k == 4 else Cita.Estado.COMPLETADA
                else:
                    estado = Cita.Estado.PENDIENTE
                cita = Cita.objects.create(
                    paciente=paciente, medico=medico,
                    fecha_hora=timezone.make_aware(inicio, tz),
                    motivo="Malestar general y control de rutina solicitado por el paciente",
                    estado=estado,
                    motivo_cancelacion="El paciente no pudo asistir por clases" if estado == Cita.Estado.CANCELADA else "",
                )
                if estado == Cita.Estado.COMPLETADA:
                    diag, trat, meds = DIAGNOSTICOS[medico.especialidad]
                    Consulta.objects.create(
                        cita=cita, diagnostico=diag, tratamiento=trat, medicamentos=meds,
                        archivos_adjuntos="Receta médica digital" if meds else "",
                        registrada_por=medico.usuario,
                    )
