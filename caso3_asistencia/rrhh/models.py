"""Modelos: Área, Empleado, Asistencia, Corrección de asistencia y Permiso."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

DIAS_VACACIONES_ANUALES = 30
JORNADA_HORAS = Decimal("8")

validar_dni = RegexValidator(r"^\d{8}$", "El DNI debe tener exactamente 8 dígitos numéricos.")


def validar_email_corporativo(valor):
    if not valor.lower().endswith("@tecnoandes.pe"):
        raise ValidationError("El email debe ser corporativo (@tecnoandes.pe).")


def validar_no_futura(fecha):
    if fecha > timezone.localdate():
        raise ValidationError("La fecha de ingreso no puede ser futura.")


class Area(models.Model):
    nombre = models.CharField("nombre", max_length=40, unique=True)
    jefe = models.ForeignKey(
        "Empleado", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="areas_a_cargo", verbose_name="jefe de área",
    )

    class Meta:
        verbose_name = "área"
        verbose_name_plural = "áreas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Empleado(models.Model):
    class Contrato(models.TextChoices):
        PLANILLA = "planilla", "Planilla"
        LOCACION = "locacion", "Locación de servicios"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="empleado", verbose_name="usuario del sistema",
    )
    dni = models.CharField("DNI", max_length=8, unique=True, validators=[validar_dni])
    nombres = models.CharField("nombres", max_length=80)
    apellidos = models.CharField("apellidos", max_length=80)
    cargo = models.CharField("cargo", max_length=80)
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="empleados", verbose_name="área")
    fecha_ingreso = models.DateField("fecha de ingreso", validators=[validar_no_futura])
    tipo_contrato = models.CharField("tipo de contrato", max_length=10, choices=Contrato.choices)
    email = models.EmailField("email corporativo", unique=True, validators=[validar_email_corporativo])
    salario = models.DecimalField("salario (S/)", max_digits=9, decimal_places=2,
                                  validators=[MinValueValidator(Decimal("1025"))])
    hora_entrada = models.TimeField("hora de entrada", default="08:00")
    hora_salida = models.TimeField("hora de salida", default="16:00")
    activo = models.BooleanField("cuenta activa", default=True)

    class Meta:
        verbose_name = "empleado"
        verbose_name_plural = "empleados"
        ordering = ["apellidos", "nombres"]

    def __str__(self):
        return f"{self.apellidos}, {self.nombres}"

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    @property
    def antiguedad(self):
        """Antigüedad en años y meses (campo calculado)."""
        hoy = timezone.localdate()
        meses = (hoy.year - self.fecha_ingreso.year) * 12 + hoy.month - self.fecha_ingreso.month
        if hoy.day < self.fecha_ingreso.day:
            meses -= 1
        anios, meses = divmod(max(meses, 0), 12)
        return f"{anios} año{'s' if anios != 1 else ''} y {meses} mes{'es' if meses != 1 else ''}"

    def dias_vacaciones_tomados(self, anio=None):
        anio = anio or timezone.localdate().year
        aprobadas = self.permisos.filter(
            tipo=Permiso.Tipo.VACACIONES, estado=Permiso.Estado.APROBADO, fecha_inicio__year=anio
        )
        return sum(p.dias for p in aprobadas)

    @property
    def dias_vacaciones_disponibles(self):
        """30 días anuales - días de vacaciones aprobados este año."""
        return DIAS_VACACIONES_ANUALES - self.dias_vacaciones_tomados()


class Asistencia(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, related_name="asistencias")
    fecha = models.DateField("fecha")
    hora_entrada = models.DateTimeField("entrada")
    hora_salida = models.DateTimeField("salida", null=True, blank=True)
    corregida = models.BooleanField("corregida por RRHH", default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "registro de asistencia"
        verbose_name_plural = "registros de asistencia"
        ordering = ["-fecha", "empleado__apellidos"]
        permissions = [
            ("registrar_asistencia", "Puede registrar su asistencia"),
            ("corregir_asistencia", "Puede corregir registros de asistencia"),
            ("ver_reportes_area", "Puede ver los reportes de su área"),
            ("ver_reportes_globales", "Puede ver los reportes de toda la empresa"),
        ]

    def __str__(self):
        return f"{self.empleado} - {self.fecha:%d/%m/%Y}"

    @property
    def horas_trabajadas(self):
        """Cálculo automático de horas trabajadas (con 2 decimales)."""
        if not self.hora_salida:
            return None
        segundos = (self.hora_salida - self.hora_entrada).total_seconds()
        return (Decimal(segundos) / Decimal(3600)).quantize(Decimal("0.01"))

    @property
    def horas_extra(self):
        """Horas por encima de la jornada de 8 horas."""
        horas = self.horas_trabajadas
        if horas is None:
            return Decimal("0")
        return max(Decimal("0"), horas - JORNADA_HORAS)

    def editable_por_empleado(self):
        """Integridad: el empleado solo puede completar su registro dentro de las 24 horas."""
        return timezone.now() - self.hora_entrada < timedelta(hours=24)


class CorreccionAsistencia(models.Model):
    class Motivo(models.TextChoices):
        ERROR_SISTEMA = "error_sistema", "Error de sistema"
        OLVIDO = "olvido", "Olvido de marcación"
        OTRO = "otro", "Otro"

    asistencia = models.ForeignKey(Asistencia, on_delete=models.CASCADE, related_name="correcciones")
    motivo = models.CharField("motivo", max_length=15, choices=Motivo.choices)
    justificacion = models.TextField("justificación")
    entrada_anterior = models.DateTimeField()
    salida_anterior = models.DateTimeField(null=True, blank=True)
    entrada_nueva = models.DateTimeField()
    salida_nueva = models.DateTimeField()
    corregido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "corrección de asistencia"
        verbose_name_plural = "correcciones de asistencia"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Corrección de {self.asistencia} ({self.get_motivo_display()})"


class Permiso(models.Model):
    class Tipo(models.TextChoices):
        PERSONAL = "personal", "Personal"
        MEDICO = "medico", "Médico"
        DUELO = "duelo", "Duelo"
        MATERNIDAD = "maternidad_paternidad", "Maternidad / paternidad"
        VACACIONES = "vacaciones", "Vacaciones"
        OTRO = "otro", "Otro"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADO = "aprobado", "Aprobado"
        RECHAZADO = "rechazado", "Rechazado"

    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, related_name="permisos")
    tipo = models.CharField("tipo", max_length=25, choices=Tipo.choices)
    fecha_inicio = models.DateField("fecha de inicio")
    fecha_fin = models.DateField("fecha de fin")
    motivo = models.TextField("motivo detallado")
    documento_adjunto = models.CharField(
        "documento adjunto (simulado)", max_length=200, blank=True,
        help_text="Descripción del documento de sustento (ej. Certificado médico N.° 4512).",
    )
    estado = models.CharField("estado", max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="permisos_revisados",
    )
    fecha_revision = models.DateTimeField("fecha de revisión", null=True, blank=True)
    comentario_revision = models.CharField("comentario de revisión", max_length=200, blank=True)
    notificado = models.BooleanField("empleado notificado", default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "permiso"
        verbose_name_plural = "permisos"
        ordering = ["-creado_en"]
        permissions = [
            ("solicitar_permiso", "Puede solicitar permisos y vacaciones"),
            ("aprobar_permiso", "Puede aprobar o rechazar permisos"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} de {self.empleado} ({self.fecha_inicio:%d/%m} al {self.fecha_fin:%d/%m})"

    @property
    def dias(self):
        return (self.fecha_fin - self.fecha_inicio).days + 1

    @property
    def color_estado(self):
        return {"pendiente": "warning", "aprobado": "success", "rechazado": "danger"}[self.estado]

    def resolver(self, aprobado, usuario, comentario=""):
        """Flujo de aprobación: pendiente -> aprobado / rechazado, y deja la notificación pendiente."""
        self.estado = self.Estado.APROBADO if aprobado else self.Estado.RECHAZADO
        self.revisado_por = usuario
        self.fecha_revision = timezone.now()
        self.comentario_revision = comentario
        self.notificado = False
        self.save()

    @staticmethod
    def superpuestos(empleado, inicio, fin, excluir_pk=None):
        """Permisos no rechazados del empleado que se cruzan con el rango [inicio, fin]."""
        return (
            Permiso.objects.filter(empleado=empleado, fecha_inicio__lte=fin, fecha_fin__gte=inicio)
            .filter(~Q(estado=Permiso.Estado.RECHAZADO))
            .exclude(pk=excluir_pk)
        )
