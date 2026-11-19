"""Login con credenciales corporativas (@tecnoandes.pe)."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm

DOMINIO = "@tecnoandes.pe"


class LoginCorporativoForm(AuthenticationForm):
    username = forms.CharField(
        label="Usuario corporativo", max_length=150,
        widget=forms.TextInput(attrs={"autofocus": True, "class": "form-control",
                                      "placeholder": "ej. aparedes", "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Contraseña", strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}),
    )

    error_messages = {
        "invalid_login": "Usuario o contraseña incorrectos.",
        "inactive": "Esta cuenta está desactivada. Comunícate con RRHH.",
    }

    def clean_username(self):
        usuario = self.cleaned_data["username"].strip().lower()
        if "@" in usuario:
            if not usuario.endswith(DOMINIO):
                raise forms.ValidationError(f"Usa tu usuario o correo corporativo ({DOMINIO}).")
            usuario = usuario.removesuffix(DOMINIO)
        return usuario

    def confirm_login_allowed(self, user):
        """Además de is_active, bloquea a empleados dados de baja."""
        super().confirm_login_allowed(user)
        empleado = getattr(user, "empleado", None)
        if empleado is not None and not empleado.activo:
            raise forms.ValidationError(self.error_messages["inactive"], code="inactive")
