"""Rutas de autenticación."""
from django.urls import path

from .views import LoginUNCPView, LogoutUNCPView

urlpatterns = [
    path("login/", LoginUNCPView.as_view(), name="login"),
    path("logout/", LogoutUNCPView.as_view(), name="logout"),
]
