"""Crea los roles jerárquicos y asigna sus permisos.

Uso: python manage.py crear_roles   (se puede repetir, no duplica)
Los empleados de prueba (con sus usuarios y roles) los crea: python manage.py poblar_datos
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from cuentas.roles import ADMIN_RRHH, CONTADOR, EMPLEADO, JEFE_AREA

CRUD = lambda modelo: [f"{a}_{modelo}" for a in ("add", "change", "delete", "view")]  # noqa: E731

PERMISOS_POR_ROL = {
    ADMIN_RRHH: {
        "rrhh": CRUD("area") + CRUD("empleado") + CRUD("asistencia") + CRUD("permiso")
        + ["view_correccionasistencia", "registrar_asistencia", "solicitar_permiso", "aprobar_permiso",
           "ver_reportes_area", "ver_reportes_globales", "corregir_asistencia"],
        "auditoria": ["view_registroauditoria"],
        "auth": ["view_user", "add_user", "change_user"],
    },
    JEFE_AREA: {
        "rrhh": ["view_empleado", "view_asistencia", "view_permiso", "registrar_asistencia",
                 "solicitar_permiso", "aprobar_permiso", "ver_reportes_area"],
    },
    EMPLEADO: {
        "rrhh": ["registrar_asistencia", "solicitar_permiso"],
    },
    CONTADOR: {
        "rrhh": ["view_asistencia", "view_empleado", "registrar_asistencia", "solicitar_permiso",
                 "ver_reportes_globales"],
    },
}

# Roles que pueden entrar al Django Admin (verán solo lo que sus permisos permiten)
ROLES_CON_ADMIN = (ADMIN_RRHH, CONTADOR)


class Command(BaseCommand):
    help = "Crea los grupos Admin RRHH, Jefe de Área, Empleado y Contador con sus permisos"

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
            self.stdout.write(f"  Rol {rol}: {len(permisos)} permisos")

        User = get_user_model()
        staff = User.objects.filter(groups__name__in=ROLES_CON_ADMIN).update(is_staff=True)
        self.stdout.write(self.style.SUCCESS(
            f"[OK] 4 roles jerárquicos con permisos; {staff} usuario(s) con acceso al admin"
        ))
