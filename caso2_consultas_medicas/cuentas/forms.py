"""Login diferenciado por tipo de usuario."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm

from auditoria.utils import registrar_evento

from .roles import ADMIN, MEDICO, PACIENTE, RECEPCIONISTA

DOMINIO = "@uncp.edu.pe"
TIPOS = [
    (PACIENTE, "Paciente (estudiante o docente)"),
    (MEDICO, "Médico"),
    (RECEPCIONISTA, "Recepcionista"),
    (ADMIN, "Administrador"),
]


class LoginTipoUsuarioForm(AuthenticationForm):
    tipo = forms.ChoiceField(
        label="Ingresar como", choices=TIPOS,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    username = forms.CharField(
        label="Usuario UNCP", max_length=150,
        widget=forms.TextInput(attrs={"autofocus": True, "class": "form-control",
                                      "placeholder": "ej. darana", "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Contraseña", strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}),
    )

    error_messages = {
        "invalid_login": "Usuario o contraseña incorrectos.",
        "inactive": "Esta cuenta está desactivada.",
    }

    field_order = ["tipo", "username", "password"]

    def clean_username(self):
        usuario = self.cleaned_data["username"].strip().lower()
        if "@" in usuario:
            if not usuario.endswith(DOMINIO):
                raise forms.ValidationError(f"Usa tu usuario o correo institucional ({DOMINIO}).")
            usuario = usuario.removesuffix(DOMINIO)
        return usuario

    def clean(self):
        datos = super().clean()  # autentica usuario y contraseña
        usuario = self.get_user()
        tipo = datos.get("tipo")
        if usuario and tipo and not usuario.is_superuser and not usuario.groups.filter(name=tipo).exists():
            registrar_evento(
                self.request, "Login con tipo de usuario incorrecto",
                detalle=f"usuario={usuario.username} intentó ingresar como {tipo}",
                nivel="WARNING", usuario=usuario,
            )
            raise forms.ValidationError(
                f"El usuario {usuario.username} no está registrado como {dict(TIPOS)[tipo]}."
            )
        return datos
