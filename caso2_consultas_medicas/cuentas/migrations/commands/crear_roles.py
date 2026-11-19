"""Crea los grupos Médicos, Recepcionistas, Pacientes y Admins con sus permisos.

Uso: python manage.py crear_roles   (se puede repetir, no duplica)
Los médicos y pacientes de prueba (con sus usuarios) los crea: python manage.py poblar_datos
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from cuentas.roles import ADMIN, MEDICO, PACIENTE, RECEPCIONISTA

PASSWORD = "Uncp2026!"

PERMISOS_POR_ROL = {
    ADMIN: {
        "consultas": [
            "add_paciente", "change_paciente", "view_paciente",
            "add_medico", "change_medico", "delete_medico", "view_medico",
            "add_cita", "change_cita", "delete_cita", "view_cita",
            "agendar_cita", "cancelar_cita", "generar_reportes",
        ],
        "auditoria": ["view_registroauditoria"],
        "auth": ["view_user", "add_user", "change_user", "view_group"],
    },
    MEDICO: {
        "consultas": [
            "view_paciente", "view_medico", "view_cita",
            "add_consulta", "view_consulta", "add_notaconsulta", "view_notaconsulta",
            "ver_historial_clinico", "cancelar_cita",
        ],
    },
    RECEPCIONISTA: {
        "consultas": [
            "add_paciente", "change_paciente", "view_paciente", "view_medico",
            "add_cita", "change_cita", "view_cita", "agendar_cita", "cancelar_cita",
        ],
    },
    PACIENTE: {
        "consultas": ["view_medico", "add_cita", "agendar_cita", "cancelar_cita"],
    },
}

# usuario, nombre, apellidos, rol
USUARIOS = [
    ("director", "Ricardo", "Huamán Espinoza", ADMIN),
    ("recepcion1", "Gladys", "Poma Cerrón", RECEPCIONISTA),
]

# Estos roles pueden entrar al Django Admin (verán solo lo que sus permisos permiten)
ROLES_CON_ADMIN = (ADMIN, MEDICO, RECEPCIONISTA)


class Command(BaseCommand):
    help = "Crea los grupos y permisos del Centro Médico y los usuarios administrativos"

    def handle(self, *args, **options):
        for rol, por_app in PERMISOS_POR_ROL.items():
            grupo, _ = Group.objects.get_or_create(name=rol)
            permisos = []
            for app, codenames in por_app.items():
                encontrados = list(Permission.objects.filter(content_type__app_label=app, codename__in=codenames))
                faltan = set(codenames) - {p.codename for p in encontrados}
                if faltan:
                    self.stdout.write(self.style.WARNING(f"  {rol}: no existen {sorted(faltan)} (¿falta migrar '{app}'?)"))
                permisos += encontrados
            grupo.permissions.set(permisos)
            self.stdout.write(f"  Grupo {rol}: {len(permisos)} permisos")

        User = get_user_model()
        for username, nombre, apellidos, rol in USUARIOS:
            user, creado = User.objects.get_or_create(username=username)
            user.first_name, user.last_name = nombre, apellidos
            user.email = f"{username}@uncp.edu.pe"
            if creado:
                user.set_password(PASSWORD)
            user.save()
            user.groups.set([Group.objects.get(name=rol)])

        actualizados = User.objects.filter(groups__name__in=ROLES_CON_ADMIN).update(is_staff=True)
        self.stdout.write(self.style.SUCCESS(
            f"[OK] 4 grupos con permisos, {len(USUARIOS)} usuarios administrativos, "
            f"{actualizados} usuarios con acceso al admin (contraseña: {PASSWORD})"
        ))
