"""Crea los grupos (roles), asigna permisos y crea los 5 usuarios de prueba.

Uso: python manage.py crear_roles   (se puede repetir, no duplica)
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from cuentas.roles import ADMIN, ASISTENTE, DOCENTE

PASSWORD = "Uncp2026!"

# rol -> {app: [permisos]}
PERMISOS_POR_ROL = {
    ADMIN: {
        "prestamos": [
            "add_equipo", "change_equipo", "delete_equipo", "view_equipo",
            "add_laboratorio", "change_laboratorio", "delete_laboratorio", "view_laboratorio",
            "add_prestamo", "change_prestamo", "delete_prestamo", "view_prestamo",
            "registrar_devolucion", "ver_todos_los_prestamos",
        ],
        "auditoria": ["view_registroauditoria"],
        "auth": ["view_user", "add_user", "change_user"],
    },
    ASISTENTE: {
        "prestamos": [
            "view_equipo", "view_laboratorio", "add_prestamo", "change_prestamo",
            "view_prestamo", "registrar_devolucion", "ver_todos_los_prestamos",
        ],
    },
    DOCENTE: {
        "prestamos": ["view_equipo", "add_prestamo"],
    },
}

# usuario, nombre, apellidos, rol, puede entrar al admin
USUARIOS = [
    ("jefe_lab", "Carlos", "Mendoza Vila", ADMIN, True),
    ("asistente1", "Lucía", "Ccanto Rojas", ASISTENTE, True),
    ("jperez", "Juan", "Pérez Rojas", DOCENTE, False),
    ("mquispe", "María", "Quispe Huamán", DOCENTE, False),
    ("rhuaman", "Rosa", "Huamán Torres", DOCENTE, False),
]


class Command(BaseCommand):
    help = "Crea los roles Administrador, Docente y Asistente con sus permisos y usuarios de prueba"

    def handle(self, *args, **options):
        for rol, por_app in PERMISOS_POR_ROL.items():
            grupo, _ = Group.objects.get_or_create(name=rol)
            permisos = []
            for app, codenames in por_app.items():
                encontrados = list(Permission.objects.filter(
                    content_type__app_label=app, codename__in=codenames
                ))
                faltan = set(codenames) - {p.codename for p in encontrados}
                if faltan:
                    self.stdout.write(self.style.WARNING(
                        f"  {rol}: no existen {sorted(faltan)} (¿falta migrar la app '{app}'?)"
                    ))
                permisos += encontrados
            grupo.permissions.set(permisos)
            self.stdout.write(f"  Rol {rol}: {len(permisos)} permisos")

        User = get_user_model()
        for username, nombre, apellidos, rol, staff in USUARIOS:
            user, creado = User.objects.get_or_create(username=username)
            user.first_name, user.last_name = nombre, apellidos
            user.email = f"{username}@uncp.edu.pe"
            user.is_staff = staff
            if creado:
                user.set_password(PASSWORD)  # se guarda hasheada (PBKDF2)
            user.save()
            user.groups.set([Group.objects.get(name=rol)])

        self.stdout.write(self.style.SUCCESS(
            f"[OK] 3 roles y {len(USUARIOS)} usuarios listos (contraseña: {PASSWORD})"
        ))
