"""Formularios con validaciones simples (clean_<campo>) y cruzadas (clean)."""
import re

from django import forms
from django.utils import timezone
from django.utils.html import strip_tags

from .models import DURACION_CITA, Cita, Consulta, Medico, Paciente

BLOQUES_PELIGROSOS = re.compile(r"<(script|style)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)


def sanitizar(texto):
    """Elimina scripts, etiquetas HTML y espacios repetidos."""
    sin_scripts = BLOQUES_PELIGROSOS.sub(" ", texto or "")
    return " ".join(strip_tags(sin_scripts).split())


class BootstrapFormMixin:
    """Agrega clases de Bootstrap y marca en rojo los campos con error."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            css = "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
            campo.widget.attrs["class"] = css

    def is_valid(self):
        valido = super().is_valid()
        for nombre in self.errors:
            if nombre in self.fields:
                self.fields[nombre].widget.attrs["class"] += " is-invalid"
        return valido


# ---------------------------------------------------------------------------
# Pacientes y médicos
# ---------------------------------------------------------------------------
class PacienteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Paciente
        fields = ["dni", "nombres", "apellidos", "fecha_nacimiento", "tipo", "codigo_uncp", "email", "alergias"]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "alergias": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_dni(self):
        dni = self.cleaned_data["dni"].strip()
        if not dni.isdigit() or len(dni) != 8:
            raise forms.ValidationError("El DNI debe tener exactamente 8 dígitos numéricos.")
        return dni

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data["fecha_nacimiento"]
        if fecha > timezone.localdate():
            raise forms.ValidationError("La fecha de nacimiento no puede ser futura.")
        if timezone.localdate().year - fecha.year > 100:
            raise forms.ValidationError("Revise la fecha: la edad supera los 100 años.")
        return fecha

    def clean_codigo_uncp(self):
        return self.cleaned_data["codigo_uncp"].strip().upper()

    def clean_nombres(self):
        return sanitizar(self.cleaned_data["nombres"]).title()

    def clean_apellidos(self):
        return sanitizar(self.cleaned_data["apellidos"]).title()

    def clean_alergias(self):
        return sanitizar(self.cleaned_data.get("alergias"))

    def clean(self):
        datos = super().clean()
        email = (datos.get("email") or "").lower()
        if datos.get("tipo") == Paciente.Tipo.ESTUDIANTE and email and not email.endswith("@uncp.edu.pe"):
            self.add_error("email", "Los estudiantes deben usar su email institucional @uncp.edu.pe.")
        return datos


class MedicoForm(BootstrapFormMixin, forms.ModelForm):
    """Usado en el Django Admin para registrar médicos."""

    class Meta:
        model = Medico
        fields = "__all__"

    def clean_cmp(self):
        cmp = self.cleaned_data["cmp"].strip()
        if not re.fullmatch(r"\d{5,6}", cmp):
            raise forms.ValidationError("Formato de CMP inválido: deben ser 5 o 6 dígitos (ej: 12345).")
        return cmp

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get("hora_inicio"), datos.get("hora_fin")
        if inicio and fin and fin <= inicio:
            self.add_error("hora_fin", "La hora de fin debe ser posterior a la de inicio.")
        return datos


# ---------------------------------------------------------------------------
# Citas
# ---------------------------------------------------------------------------
class CitaForm(BootstrapFormMixin, forms.ModelForm):
    """Agendamiento de cita médica (ModelForm con validaciones cruzadas)."""

    class Meta:
        model = Cita
        fields = ["paciente", "medico", "fecha_hora", "motivo"]
        widgets = {
            "fecha_hora": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "motivo": forms.Textarea(attrs={"rows": 3, "placeholder": "Describa sus síntomas (mínimo 20 caracteres)"}),
        }
        help_texts = {"fecha_hora": "Cada cita dura 30 minutos."}

    def __init__(self, *args, usuario=None, especialidad=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        medicos = Medico.objects.all()
        if especialidad:
            medicos = medicos.filter(especialidad=especialidad)
        self.fields["medico"].queryset = medicos
        self.fields["medico"].label_from_instance = (
            lambda m: f"Dr(a). {m.nombres} {m.apellidos} - {m.get_especialidad_display()} ({m.horario})"
        )

        paciente_propio = getattr(usuario, "paciente", None) if usuario else None
        if paciente_propio:
            # El paciente agenda sus propias citas
            del self.fields["paciente"]
            self.instance.paciente = paciente_propio

    def clean_fecha_hora(self):
        fecha_hora = self.cleaned_data["fecha_hora"]
        if fecha_hora <= timezone.now():
            raise forms.ValidationError("La cita debe agendarse en una fecha y hora futuras.")
        return fecha_hora

    def clean_motivo(self):
        motivo = sanitizar(self.cleaned_data["motivo"])
        if len(motivo) < 20:
            raise forms.ValidationError(
                f"El motivo debe tener al menos 20 caracteres (escribiste {len(motivo)})."
            )
        return motivo

    def clean(self):
        datos = super().clean()
        paciente = datos.get("paciente") or getattr(self.instance, "paciente", None)
        medico = datos.get("medico")
        inicio = datos.get("fecha_hora")
        if not (medico and inicio):
            return datos

        local = timezone.localtime(inicio)
        activas = Cita.objects.exclude(estado=Cita.Estado.CANCELADA).exclude(pk=self.instance.pk)

        # 1. El horario del médico
        if not (medico.hora_inicio <= local.time() and (local + DURACION_CITA).time() <= medico.hora_fin):
            self.add_error("fecha_hora", f"El médico atiende de {medico.horario}.")

        # 2. El médico no puede tener citas superpuestas (cada cita dura 30 min)
        cruce = activas.filter(
            medico=medico,
            fecha_hora__gt=inicio - DURACION_CITA,
            fecha_hora__lt=inicio + DURACION_CITA,
        ).first()
        if cruce:
            self.add_error(
                "fecha_hora",
                f"El horario está ocupado: el médico ya tiene una cita a las "
                f"{timezone.localtime(cruce.fecha_hora):%H:%M}.",
            )

        # 3. El paciente no puede tener 2 citas el mismo día
        if paciente and activas.filter(paciente=paciente, fecha_hora__date=local.date()).exists():
            raise forms.ValidationError(
                f"{paciente.nombre_completo} ya tiene una cita el {local:%d/%m/%Y}. "
                "No se permiten dos citas el mismo día."
            )
        return datos

    def save(self, commit=True):
        cita = super().save(commit=False)
        cita.creada_por = self.usuario
        if commit:
            cita.save()
        return cita


class CancelacionForm(BootstrapFormMixin, forms.Form):
    """Formulario clásico para cancelar una cita."""

    motivo = forms.CharField(
        label="Motivo de la cancelación", max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Ej. Viaje por motivos familiares"}),
    )

    def clean_motivo(self):
        motivo = sanitizar(self.cleaned_data["motivo"])
        if len(motivo) < 10:
            raise forms.ValidationError("Indique el motivo con al menos 10 caracteres.")
        return motivo


# ---------------------------------------------------------------------------
# Consulta médica (post-atención) y notas
# ---------------------------------------------------------------------------
class ConsultaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Consulta
        fields = ["diagnostico", "tratamiento", "medicamentos", "proxima_cita", "archivos_adjuntos"]
        widgets = {
            "diagnostico": forms.Textarea(attrs={"rows": 3}),
            "tratamiento": forms.Textarea(attrs={"rows": 3}),
            "medicamentos": forms.Textarea(attrs={"rows": 2}),
            "proxima_cita": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "archivos_adjuntos": forms.Textarea(attrs={"rows": 2, "placeholder": "Ej. Receta N.° 1234, Hemograma completo"}),
        }

    def clean_diagnostico(self):
        texto = sanitizar(self.cleaned_data["diagnostico"])
        if len(texto) < 10:
            raise forms.ValidationError("El diagnóstico debe tener al menos 10 caracteres.")
        return texto

    def clean_tratamiento(self):
        return sanitizar(self.cleaned_data["tratamiento"])

    def clean_medicamentos(self):
        return sanitizar(self.cleaned_data.get("medicamentos"))

    def clean_archivos_adjuntos(self):
        return sanitizar(self.cleaned_data.get("archivos_adjuntos"))

    def clean_proxima_cita(self):
        fecha = self.cleaned_data.get("proxima_cita")
        if fecha and fecha <= timezone.localdate():
            raise forms.ValidationError("La próxima cita de control debe ser una fecha futura.")
        return fecha


class NotaForm(BootstrapFormMixin, forms.Form):
    """Formulario clásico: la única forma de complementar una consulta ya registrada."""

    texto = forms.CharField(label="Nueva nota", widget=forms.Textarea(attrs={"rows": 2}))

    def clean_texto(self):
        texto = sanitizar(self.cleaned_data["texto"])
        if len(texto) < 10:
            raise forms.ValidationError("La nota debe tener al menos 10 caracteres.")
        return texto
