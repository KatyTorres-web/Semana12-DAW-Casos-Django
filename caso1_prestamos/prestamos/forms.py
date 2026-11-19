"""Formularios: ModelForm de préstamo y formulario clásico de devolución."""
import re
from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.html import strip_tags

from cuentas.roles import DOCENTE

from .models import Equipo, Prestamo

MAX_PRESTAMOS_ACTIVOS = 3


# Bloques <script> y <style> completos (etiqueta + contenido)
BLOQUES_PELIGROSOS = re.compile(r"<(script|style)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)


def sanitizar(texto):
    """Elimina scripts, etiquetas HTML y espacios repetidos."""
    sin_scripts = BLOQUES_PELIGROSOS.sub(" ", texto or "")
    return " ".join(strip_tags(sin_scripts).split())


class BootstrapFormMixin:
    """Agrega clases de Bootstrap a los widgets y marca los campos con error."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.Select):
                css = "form-select"
            elif isinstance(campo.widget, forms.CheckboxInput):
                css = "form-check-input"
            else:
                css = "form-control"
            campo.widget.attrs["class"] = css

    def is_valid(self):
        valido = super().is_valid()
        for nombre in self.errors:
            if nombre in self.fields:
                self.fields[nombre].widget.attrs["class"] += " is-invalid"
        return valido


class PrestamoForm(BootstrapFormMixin, forms.ModelForm):
    """Solicitud / registro de préstamo (ModelForm)."""

    class Meta:
        model = Prestamo
        fields = [
            "docente", "equipo", "cantidad",
            "fecha_prestamo", "fecha_devolucion_prevista", "observaciones",
        ]
        widgets = {
            "fecha_prestamo": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_devolucion_prevista": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "cantidad": "Unidades del mismo equipo.",
            "observaciones": "Opcional. Se eliminan etiquetas HTML.",
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        hoy = timezone.localdate()
        self.fields["fecha_prestamo"].initial = hoy
        self.fields["fecha_devolucion_prevista"].initial = hoy + timedelta(days=7)
        self.fields["equipo"].queryset = Equipo.objects.select_related("laboratorio")

        puede_elegir_docente = usuario and usuario.has_perm("prestamos.ver_todos_los_prestamos")
        if puede_elegir_docente:
            # Asistente / Administrador: registra el préstamo a nombre de un docente
            User = get_user_model()
            self.fields["docente"].queryset = User.objects.filter(
                groups__name=DOCENTE, is_active=True
            ).order_by("last_name")
            self.fields["docente"].label_from_instance = (
                lambda u: f"{u.get_full_name() or u.username} ({u.username})"
            )
        else:
            # Docente: el préstamo siempre es para él mismo
            del self.fields["docente"]
            self.instance.docente = usuario

    # ---------- Validaciones por campo: clean_<campo>() ----------
    def clean_equipo(self):
        equipo = self.cleaned_data["equipo"]
        if equipo.estado != Equipo.Estado.OPERATIVO:
            raise forms.ValidationError(
                f'El equipo {equipo.codigo_patrimonial} está "{equipo.get_estado_display()}". '
                "Solo se prestan equipos operativos."
            )
        return equipo

    def clean_fecha_prestamo(self):
        fecha = self.cleaned_data["fecha_prestamo"]
        if fecha < timezone.localdate():
            raise forms.ValidationError("La fecha de préstamo no puede ser anterior a hoy.")
        return fecha

    def clean_observaciones(self):
        return sanitizar(self.cleaned_data.get("observaciones"))

    # ---------- Validaciones cruzadas: clean() ----------
    def clean(self):
        datos = super().clean()
        docente = datos.get("docente") or getattr(self.instance, "docente", None)
        equipo = datos.get("equipo")
        cantidad = datos.get("cantidad")
        inicio = datos.get("fecha_prestamo")
        fin = datos.get("fecha_devolucion_prevista")

        if inicio and fin and fin <= inicio:
            self.add_error(
                "fecha_devolucion_prevista",
                "La fecha de devolución debe ser posterior a la fecha de préstamo.",
            )

        if docente:
            activos = Prestamo.objects.filter(
                docente=docente, estado=Prestamo.Estado.ACTIVO
            ).count()
            if activos >= MAX_PRESTAMOS_ACTIVOS:
                raise forms.ValidationError(
                    f"{docente.get_full_name() or docente.username} ya tiene {activos} "
                    f"préstamos activos. El máximo permitido es {MAX_PRESTAMOS_ACTIVOS}. "
                    "Debe devolver un equipo antes de solicitar otro."
                )

        if equipo and cantidad and equipo.estado == Equipo.Estado.OPERATIVO:
            disponibles = equipo.cantidad_disponible
            if cantidad > disponibles:
                self.add_error(
                    "cantidad",
                    f"Solo hay {disponibles} unidad(es) disponible(s) de "
                    f"{equipo.nombre} (de {equipo.cantidad_total}).",
                )
        return datos

    def save(self, commit=True):
        prestamo = super().save(commit=False)
        prestamo.registrado_por = self.usuario
        if commit:
            prestamo.save()
        return prestamo


class DevolucionForm(BootstrapFormMixin, forms.Form):
    """Registro de devolución (formulario clásico, no ModelForm)."""

    fecha_devolucion = forms.DateField(
        label="Fecha de devolución",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    estado_retorno = forms.ChoiceField(
        label="Estado del equipo al retornar", choices=Equipo.Estado.choices
    )
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Obligatorio si el equipo vuelve con fallas. Se eliminan etiquetas HTML.",
    )

    def __init__(self, *args, prestamo, **kwargs):
        super().__init__(*args, **kwargs)
        self.prestamo = prestamo
        self.fields["fecha_devolucion"].initial = timezone.localdate()

    def clean_fecha_devolucion(self):
        fecha = self.cleaned_data["fecha_devolucion"]
        if fecha < self.prestamo.fecha_prestamo:
            raise forms.ValidationError(
                "La devolución no puede ser anterior a la fecha del préstamo "
                f"({self.prestamo.fecha_prestamo:%d/%m/%Y})."
            )
        if fecha > timezone.localdate():
            raise forms.ValidationError("La fecha de devolución no puede ser futura.")
        return fecha

    def clean_observaciones(self):
        return sanitizar(self.cleaned_data.get("observaciones"))

    def clean(self):
        datos = super().clean()
        estado = datos.get("estado_retorno")
        if estado and estado != Equipo.Estado.OPERATIVO and not datos.get("observaciones"):
            self.add_error(
                "observaciones", "Describe la falla si el equipo no vuelve operativo."
            )
        return datos
