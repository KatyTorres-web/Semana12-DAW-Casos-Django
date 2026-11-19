"""Login y logout."""
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView

from .forms import LoginUNCPForm


class LoginUNCPView(LoginView):
    form_class = LoginUNCPForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        usuario = form.get_user()
        messages.success(self.request, f"Bienvenido(a), {usuario.get_full_name() or usuario.username}.")
        return respuesta


class LogoutUNCPView(LogoutView):
    """Cierre de sesión solo por POST (protegido con CSRF)."""
    http_method_names = ["post", "options"]
