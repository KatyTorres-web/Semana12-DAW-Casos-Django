"""Formularios: marcación, corrección (solo RRHH), permisos, revisión y empleados."""
import re

from django import forms
from django.utils import timezone
from django.utils.html import strip_tags

from .models import Asistencia, CorreccionAsistencia, Empleado, Permiso

BLOQUES_PELIGROSOS = re.compile(r"<(script|style)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)


def sanitizar(texto):
    """Elimina scripts, etiquetas HTML y espacios repetidos."""
    sin_scripts = BLOQUES_PELIGROSOS.sub(" ", texto or "")
    return " ".join(strip_tags(sin_scripts).split())


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, (forms.RadioSelect, forms.HiddenInput)):
                continue
            css = "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
            campo.widget.attrs["class"] = css

    def is_valid(self):
        valido = super().is_valid()
        for nombre in self.errors:
            if nombre in self.fields and "class" in self.fields[nombre].widget.attrs:
                self.fields[nombre].widget.attrs["class"] += " is-invalid"
        return valido


# ---------------------------------------------------------------------------
# Asistencia
# ---------------------------------------------------------------------------
class MarcacionForm(forms.Form):
    """Marcación de entrada/salida. La hora la pone el sistema al enviar (timestamp)."""

    tipo = forms.ChoiceField(choices=[("entrada", "Entrada"), ("salida", "Salida")], widget=forms.HiddenInput)

    def __init__(self, *args, empleado, **kwargs):
        super().__init__(*args, **kwargs)
        self.empleado = empleado
        self.ahora = timezone.now()
        self.abierta = (
            Asistencia.objects.filter(empleado=empleado, hora_salida__isnull=True)
            .order_by("-hora_entrada").first()
        )

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo")
        hoy = timezone.localdate()
        if tipo == "entrada":
            if self.abierta and self.abierta.fecha == hoy:
                raise forms.ValidationError(
                    f"Ya registraste tu entrada a las {timezone.localtime(self.abierta.hora_entrada):%H:%M} "
                    "y aún no marcas la salida."
                )
        elif tipo == "salida":
            if not self.abierta:
                raise forms.ValidationError("No tienes una entrada abierta: marca primero tu entrada.")
            if not self.abierta.editable_por_empleado() or self.abierta.fecha != hoy:
                raise forms.ValidationError(
                    f"Tu entrada del {self.abierta.fecha:%d/%m/%Y} quedó sin salida y ya pasaron más de "
                    "24 horas. Solicita a RRHH una corrección de asistencia."
                )
            if self.ahora <= self.abierta.hora_entrada:
                raise forms.ValidationError("La hora de salida debe ser posterior a la de entrada.")
        return datos

    def guardar(self):
        """Crea la entrada o cierra el registro con la hora actual del servidor."""
        if self.cleaned_data["tipo"] == "entrada":
            return Asistencia.objects.create(
                empleado=self.empleado, fecha=timezone.localdate(), hora_entrada=self.ahora
            )
        self.abierta.hora_salida = self.ahora
        self.abierta.save(update_fields=["hora_salida"])
        return self.abierta


class CorreccionAsistenciaForm(BootstrapFormMixin, forms.ModelForm):
    """Solo RRHH: corrige un registro con justificación obligatoria."""

    class Meta:
        model = CorreccionAsistencia
        fields = ["entrada_nueva", "salida_nueva", "motivo", "justificacion"]
        widgets = {
            "entrada_nueva": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "salida_nueva": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "justificacion": forms.Textarea(attrs={"rows": 3, "placeholder": "Mínimo 50 caracteres"}),
        }
        labels = {"entrada_nueva": "Entrada corregida", "salida_nueva": "Salida corregida"}

    def __init__(self, *args, asistencia, **kwargs):
        super().__init__(*args, **kwargs)
        self.asistencia = asistencia
        self.fields["entrada_nueva"].initial = timezone.localtime(asistencia.hora_entrada)
        if asistencia.hora_salida:
            self.fields["salida_nueva"].initial = timezone.localtime(asistencia.hora_salida)

    def clean_justificacion(self):
        texto = sanitizar(self.cleaned_data["justificacion"])
        if len(texto) < 50:
            raise forms.ValidationError(f"La justificación debe tener al menos 50 caracteres (tiene {len(texto)}).")
        return texto

    def clean_entrada_nueva(self):
        entrada = self.cleaned_data["entrada_nueva"]
        if timezone.localtime(entrada).date() != self.asistencia.fecha:
            raise forms.ValidationError(f"La entrada debe ser del mismo día del registro ({self.asistencia.fecha:%d/%m/%Y}).")
        return entrada

    def clean(self):
        datos = super().clean()
        entrada, salida = datos.get("entrada_nueva"), datos.get("salida_nueva")
        if entrada and salida and salida <= entrada:
            self.add_error("salida_nueva", "La hora de salida debe ser posterior a la de entrada.")
        return datos

    def save(self, usuario):
        """Guarda la corrección (con los valores anteriores) y actualiza el registro."""
        correccion = super().save(commit=False)
        correccion.asistencia = self.asistencia
        correccion.entrada_anterior = self.asistencia.hora_entrada
        correccion.salida_anterior = self.asistencia.hora_salida
        correccion.corregido_por = usuario
        correccion.save()
        self.asistencia.hora_entrada = correccion.entrada_nueva
        self.asistencia.hora_salida = correccion.salida_nueva
        self.asistencia.corregida = True
        self.asistencia.save()
        return correccion


# ---------------------------------------------------------------------------
# Permisos
# ---------------------------------------------------------------------------
class PermisoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Permiso
        fields = ["tipo", "fecha_inicio", "fecha_fin", "motivo", "documento_adjunto"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "motivo": forms.Textarea(attrs={"rows": 3, "placeholder": "Mínimo 30 caracteres"}),
        }

    def __init__(self, *args, empleado, **kwargs):
        super().__init__(*args, **kwargs)
        self.empleado = empleado
        self.instance.empleado = empleado

    def clean_motivo(self):
        motivo = sanitizar(self.cleaned_data["motivo"])
        if len(motivo) < 30:
            raise forms.ValidationError(f"Describe el motivo con al menos 30 caracteres (tiene {len(motivo)}).")
        return motivo

    def clean_documento_adjunto(self):
        return sanitizar(self.cleaned_data.get("documento_adjunto"))

    def clean(self):
        datos = super().clean()
        tipo, inicio, fin = datos.get("tipo"), datos.get("fecha_inicio"), datos.get("fecha_fin")
        if not (inicio and fin):
            return datos
        if fin < inicio:
            self.add_error("fecha_fin", "La fecha de fin debe ser igual o posterior a la de inicio.")
            return datos

        cruce = Permiso.superpuestos(self.empleado, inicio, fin, excluir_pk=self.instance.pk).first()
        if cruce:
            raise forms.ValidationError(
                f"Ya tienes un permiso {cruce.get_estado_display().lower()} que se cruza con esas fechas: {cruce}."
            )

        dias = (fin - inicio).days + 1
        if tipo == Permiso.Tipo.VACACIONES:
            disponibles = self.empleado.dias_vacaciones_disponibles
            if dias > disponibles:
                self.add_error("fecha_fin", f"Solicitas {dias} días de vacaciones y solo tienes {disponibles} disponibles.")
        if tipo == Permiso.Tipo.MEDICO and not datos.get("documento_adjunto"):
            self.add_error("documento_adjunto", "Los permisos médicos requieren describir el certificado médico.")
        return datos


class RevisionPermisoForm(BootstrapFormMixin, forms.Form):
    """Formulario clásico para aprobar o rechazar."""

    decision = forms.ChoiceField(
        label="Decisión", choices=[("aprobar", "Aprobar"), ("rechazar", "Rechazar")],
        widget=forms.RadioSelect,
    )
    comentario = forms.CharField(label="Comentario", max_length=200, required=False)

    def clean_comentario(self):
        return sanitizar(self.cleaned_data.get("comentario"))

    def clean(self):
        datos = super().clean()
        if datos.get("decision") == "rechazar" and len(datos.get("comentario", "")) < 10:
            self.add_error("comentario", "Explica el motivo del rechazo (mínimo 10 caracteres).")
        return datos


# ---------------------------------------------------------------------------
# Empleados (usado en el Django Admin)
# ---------------------------------------------------------------------------
class EmpleadoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Empleado
        fields = "__all__"

    def clean_dni(self):
        dni = self.cleaned_data["dni"].strip()
        if not re.fullmatch(r"\d{8}", dni):
            raise forms.ValidationError("El DNI debe tener exactamente 8 dígitos numéricos.")
        if Empleado.objects.filter(dni=dni).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe un empleado con este DNI.")
        return dni

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if not email.endswith("@tecnoandes.pe"):
            raise forms.ValidationError("El email debe ser corporativo (@tecnoandes.pe).")
        return email

    def clean_fecha_ingreso(self):
        fecha = self.cleaned_data["fecha_ingreso"]
        if fecha > timezone.localdate():
            raise forms.ValidationError("La fecha de ingreso no puede ser futura.")
        return fecha

    def clean_cargo(self):
        cargo = sanitizar(self.cleaned_data.get("cargo"))
        if not cargo:
            raise forms.ValidationError("El cargo no puede estar vacío.")
        return cargo

    def clean(self):
        datos = super().clean()
        entrada, salida = datos.get("hora_entrada"), datos.get("hora_salida")
        if entrada and salida and salida <= entrada:
            self.add_error("hora_salida", "La hora de salida debe ser posterior a la de entrada.")
        return datos
