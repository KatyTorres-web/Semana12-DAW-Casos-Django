"""Datos de prueba: 5 laboratorios, 12 equipos, 3 docentes y 15 préstamos.

Uso: python manage.py poblar_datos   (se puede repetir, no duplica)
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone

from cuentas.roles import ASISTENTE, DOCENTE
from prestamos.models import Equipo, Laboratorio, Prestamo

PASSWORD = "Uncp2026!"

DOCENTES = [
    ("jperez", "Juan", "Pérez Rojas"),
    ("mquispe", "María", "Quispe Huamán"),
    ("rhuaman", "Rosa", "Huamán Torres"),
]

LABORATORIOS = [
    ("Laboratorio 1 - Redes", "Pabellón FIS, 1er piso"),
    ("Laboratorio 2 - Software", "Pabellón FIS, 2do piso"),
    ("Laboratorio 3 - Hardware", "Pabellón FIS, 2do piso"),
    ("Laboratorio 4 - Robótica", "Pabellón FIS, 3er piso"),
    ("Laboratorio 5 - Multimedia", "Pabellón FIS, 3er piso"),
]

# código, nombre, marca, modelo, categoría, estado, laboratorio, unidades, días desde mantenimiento
EQUIPOS = [
    ("LAB-0001", "Laptop ThinkPad E14", "Lenovo", "E14 Gen 5", "laptop", "operativo", 1, 8, 40),
    ("LAB-0002", "Laptop HP ProBook 450", "HP", "450 G9", "laptop", "operativo", 1, 6, 95),
    ("LAB-0003", "Proyector Epson PowerLite", "Epson", "X49", "proyector", "operativo", 4, 3, 120),
    ("LAB-0004", "Proyector ViewSonic", "ViewSonic", "PA503S", "proyector", "mantenimiento", 4, 2, 5),
    ("LAB-0005", "Cámara Canon EOS", "Canon", "EOS Rebel T7", "camara", "operativo", 4, 2, 60),
    ("LAB-0006", "Kit Arduino Uno R3", "Arduino", "Uno R3 Starter", "arduino", "operativo", 3, 5, 30),
    ("LAB-0007", "Kit Arduino Mega", "Arduino", "Mega 2560", "arduino", "operativo", 3, 4, 200),
    ("LAB-0008", "Router Cisco ISR", "Cisco", "ISR 4321", "router", "operativo", 0, 4, 150),
    ("LAB-0009", "Router MikroTik", "MikroTik", "hEX RB750Gr3", "router", "operativo", 0, 6, 75),
    ("LAB-0010", "Switch Cisco Catalyst", "Cisco", "Catalyst 2960", "switch", "operativo", 0, 5, 210),
    ("LAB-0011", "Switch TP-Link", "TP-Link", "TL-SG108", "switch", "baja", 0, 2, 400),
    ("LAB-0012", "Cámara web Logitech", "Logitech", "C920", "camara", "operativo", 2, 6, 20),
]

# docente, equipo, cantidad, hace N días, plazo en días, devuelto tras N días (None = activo), estado retorno
PRESTAMOS = [
    # Activos (jperez llega al máximo de 3; uno vencido)
    (0, "LAB-0006", 5, 10, 7, None, ""),
    (0, "LAB-0003", 1, 2, 5, None, ""),
    (0, "LAB-0001", 2, 1, 7, None, ""),
    (1, "LAB-0008", 2, 12, 7, None, ""),
    (1, "LAB-0005", 1, 3, 7, None, ""),
    (2, "LAB-0010", 2, 1, 14, None, ""),
    # Devueltos
    (0, "LAB-0002", 3, 40, 7, 6, "operativo"),
    (1, "LAB-0012", 2, 35, 7, 9, "operativo"),
    (2, "LAB-0004", 1, 30, 5, 5, "mantenimiento"),
    (0, "LAB-0009", 3, 28, 7, 7, "operativo"),
    (1, "LAB-0007", 2, 25, 7, 6, "operativo"),
    (2, "LAB-0001", 4, 21, 7, 7, "operativo"),
    (0, "LAB-0005", 1, 18, 3, 3, "operativo"),
    (1, "LAB-0010", 3, 15, 7, 8, "operativo"),
    (2, "LAB-0003", 1, 8, 2, 2, "operativo"),
]


class Command(BaseCommand):
    help = "Carga laboratorios, equipos, docentes y préstamos de prueba"

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        User = get_user_model()

        grupo_docente, _ = Group.objects.get_or_create(name=DOCENTE)
        docentes = []
        for username, nombre, apellidos in DOCENTES:
            user, creado = User.objects.get_or_create(
                username=username,
                defaults={"first_name": nombre, "last_name": apellidos,
                          "email": f"{username}@uncp.edu.pe"},
            )
            if creado:
                user.set_password(PASSWORD)
                user.save()
            user.groups.add(grupo_docente)
            docentes.append(user)

        labs = [
            Laboratorio.objects.get_or_create(nombre=n, defaults={"ubicacion": u})[0]
            for n, u in LABORATORIOS
        ]

        for cod, nombre, marca, modelo, cat, estado, lab, cant, dias in EQUIPOS:
            Equipo.objects.update_or_create(
                codigo_patrimonial=cod,
                defaults={
                    "nombre": nombre, "marca": marca, "modelo": modelo, "categoria": cat,
                    "estado": estado, "laboratorio": labs[lab], "cantidad_total": cant,
                    "fecha_ultimo_mantenimiento": hoy - timedelta(days=dias),
                },
            )

        if Prestamo.objects.exists():
            self.stdout.write("Los préstamos ya existían: no se crean de nuevo.")
        else:
            asistente = User.objects.filter(groups__name=ASISTENTE).first()
            for doc, cod, cant, hace, plazo, devuelto, estado_ret in PRESTAMOS:
                inicio = hoy - timedelta(days=hace)
                Prestamo.objects.create(
                    docente=docentes[doc],
                    equipo=Equipo.objects.get(codigo_patrimonial=cod),
                    cantidad=cant,
                    fecha_prestamo=inicio,
                    fecha_devolucion_prevista=inicio + timedelta(days=plazo),
                    fecha_devolucion_real=inicio + timedelta(days=devuelto) if devuelto else None,
                    estado="devuelto" if devuelto else "activo",
                    estado_retorno=estado_ret,
                    observaciones_devolucion="Lámpara con poco brillo" if estado_ret == "mantenimiento" else "",
                    registrado_por=asistente,
                )

        self.stdout.write(self.style.SUCCESS(
            f"[OK] {Laboratorio.objects.count()} laboratorios, {Equipo.objects.count()} equipos, "
            f"{len(docentes)} docentes, {Prestamo.objects.count()} préstamos "
            f"(contraseña de los docentes: {PASSWORD})"
        ))
