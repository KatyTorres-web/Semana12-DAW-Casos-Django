"""Formulario de login con usuario institucional UNCP."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm

DOMINIO = "@uncp.edu.pe"


class LoginUNCPForm(AuthenticationForm):
    """Acepta 'jperez' o 'jperez@uncp.edu.pe'; rechaza otros dominios."""

    username = forms.CharField(
        label="Usuario UNCP",
        max_length=150,
        widget=forms.TextInput(attrs={
            "autofocus": True, "class": "form-control", "placeholder": "ej. jperez",
            "autocomplete": "username",
        }),
    )
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}),
    )

    error_messages = {
        "invalid_login": "Usuario o contraseña incorrectos.",
        "inactive": "Esta cuenta está desactivada.",
    }

    def clean_username(self):
        usuario = self.cleaned_data["username"].strip().lower()
        if "@" in usuario:
            if not usuario.endswith(DOMINIO):
                raise forms.ValidationError(f"Usa tu usuario o correo institucional ({DOMINIO}).")
            usuario = usuario.removesuffix(DOMINIO)
        return usuario
