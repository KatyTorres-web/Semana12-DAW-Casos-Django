"""Modelos: Paciente, Médico, Cita, Consulta y NotaConsulta."""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

DURACION_CITA = timedelta(minutes=30)

validar_dni = RegexValidator(r"^\d{8}$", "El DNI debe tener exactamente 8 dígitos numéricos.")
validar_cmp = RegexValidator(r"^\d{5,6}$", "El CMP debe tener 5 o 6 dígitos (ej: 12345).")


def validar_fecha_no_futura(fecha):
    if fecha > timezone.localdate():
        raise ValidationError("La fecha de nacimiento no puede ser futura.")


class Paciente(models.Model):
    class Tipo(models.TextChoices):
        ESTUDIANTE = "estudiante", "Estudiante"
        DOCENTE = "docente", "Docente"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="paciente", verbose_name="usuario del sistema",
    )
    dni = models.CharField("DNI", max_length=8, unique=True, validators=[validar_dni])
    nombres = models.CharField("nombres", max_length=80)
    apellidos = models.CharField("apellidos", max_length=80)
    fecha_nacimiento = models.DateField("fecha de nacimiento", validators=[validar_fecha_no_futura])
    tipo = models.CharField("tipo", max_length=12, choices=Tipo.choices)
    codigo_uncp = models.CharField("código UNCP", max_length=12, unique=True)
    email = models.EmailField("email institucional")
    alergias = models.TextField("alergias conocidas", blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "paciente"
        verbose_name_plural = "pacientes"
        ordering = ["apellidos", "nombres"]

    def __str__(self):
        return f"{self.apellidos}, {self.nombres} (DNI {self.dni})"

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    @property
    def edad(self):
        hoy = timezone.localdate()
        n = self.fecha_nacimiento
        return hoy.year - n.year - ((hoy.month, hoy.day) < (n.month, n.day))

    def clean(self):
        """Regla del negocio: los estudiantes usan obligatoriamente su email @uncp.edu.pe."""
        if self.tipo == self.Tipo.ESTUDIANTE and self.email and not self.email.lower().endswith("@uncp.edu.pe"):
            raise ValidationError({"email": "Los estudiantes deben usar su email institucional @uncp.edu.pe."})


class Medico(models.Model):
    class Especialidad(models.TextChoices):
        MEDICINA_GENERAL = "medicina_general", "Medicina general"
        ODONTOLOGIA = "odontologia", "Odontología"
        PSICOLOGIA = "psicologia", "Psicología"
        NUTRICION = "nutricion", "Nutrición"
        OBSTETRICIA = "obstetricia", "Obstetricia"
        OFTALMOLOGIA = "oftalmologia", "Oftalmología"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="medico", verbose_name="usuario del sistema",
    )
    cmp = models.CharField("CMP", max_length=6, unique=True, validators=[validar_cmp])
    nombres = models.CharField("nombres", max_length=80)
    apellidos = models.CharField("apellidos", max_length=80)
    especialidad = models.CharField("especialidad", max_length=20, choices=Especialidad.choices)
    consultorio = models.CharField("consultorio", max_length=30)
    hora_inicio = models.TimeField("inicio de atención")
    hora_fin = models.TimeField("fin de atención")

    class Meta:
        verbose_name = "médico"
        verbose_name_plural = "médicos"
        ordering = ["apellidos"]

    def __str__(self):
        return f"Dr(a). {self.nombres} {self.apellidos} - {self.get_especialidad_display()}"

    @property
    def horario(self):
        return f"{self.hora_inicio:%H:%M} - {self.hora_fin:%H:%M}"

    def clean(self):
        if self.hora_inicio and self.hora_fin and self.hora_fin <= self.hora_inicio:
            raise ValidationError({"hora_fin": "La hora de fin debe ser posterior a la de inicio."})


class Cita(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        COMPLETADA = "completada", "Completada"
        CANCELADA = "cancelada", "Cancelada"

    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, related_name="citas")
    medico = models.ForeignKey(Medico, on_delete=models.PROTECT, related_name="citas", verbose_name="médico")
    fecha_hora = models.DateTimeField("fecha y hora")
    motivo = models.TextField("motivo de consulta")
    estado = models.CharField("estado", max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    motivo_cancelacion = models.CharField("motivo de cancelación", max_length=200, blank=True)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="citas_creadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "cita"
        verbose_name_plural = "citas"
        ordering = ["fecha_hora"]
        permissions = [
            ("agendar_cita", "Puede agendar citas"),
            ("cancelar_cita", "Puede cancelar citas"),
            ("generar_reportes", "Puede generar reportes estadísticos"),
        ]

    def __str__(self):
        return f"{timezone.localtime(self.fecha_hora):%d/%m/%Y %H:%M} - {self.paciente.nombre_completo}"

    @property
    def fin(self):
        return self.fecha_hora + DURACION_CITA

    @property
    def color_estado(self):
        return {"pendiente": "primary", "completada": "success", "cancelada": "secondary"}[self.estado]


class Consulta(models.Model):
    """Registro clínico post-atención. Una vez guardado NO se modifica (solo se agregan notas)."""

    cita = models.OneToOneField(Cita, on_delete=models.PROTECT, related_name="consulta")
    diagnostico = models.TextField("diagnóstico")
    tratamiento = models.TextField("tratamiento")
    medicamentos = models.TextField("medicamentos recetados", blank=True)
    proxima_cita = models.DateField("próxima cita de control", null=True, blank=True)
    archivos_adjuntos = models.TextField(
        "archivos adjuntos (simulado)", blank=True,
        help_text="Describa las recetas o exámenes adjuntos.",
    )
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="consultas_registradas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "consulta"
        verbose_name_plural = "consultas"
        ordering = ["-creado_en"]
        permissions = [("ver_historial_clinico", "Puede ver historiales clínicos")]

    def __str__(self):
        return f"Consulta de {self.cita.paciente.nombre_completo} ({self.creado_en:%d/%m/%Y})"

    def save(self, *args, **kwargs):
        if self.pk and Consulta.objects.filter(pk=self.pk).exists():
            raise ValidationError("Una consulta registrada no se puede modificar. Agregue una nota.")
        super().save(*args, **kwargs)


class NotaConsulta(models.Model):
    consulta = models.ForeignKey(Consulta, on_delete=models.CASCADE, related_name="notas")
    texto = models.TextField("nota")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "nota de consulta"
        verbose_name_plural = "notas de consulta"
        ordering = ["creado_en"]

    def __str__(self):
        return f"Nota del {self.creado_en:%d/%m/%Y %H:%M}"
