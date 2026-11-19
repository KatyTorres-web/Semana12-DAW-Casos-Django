"""
Configuración del proyecto: Sistema de Gestión de Préstamos de Equipos (FIS-UNCP).

Integrante 2: seguridad, sesiones, middleware de auditoría y logging.
"""
import os
from pathlib import Path

from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Seguridad básica
# ---------------------------------------------------------------------------
# La SECRET_KEY nunca se escribe en el código. Se toma de la variable de
# entorno DJANGO_SECRET_KEY o, en desarrollo, se genera una vez y se guarda en
# el archivo local .secret_key (incluido en .gitignore).
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY_FILE = BASE_DIR / ".secret_key"
    if not SECRET_KEY_FILE.exists():
        SECRET_KEY_FILE.write_text(get_random_secret_key())
    SECRET_KEY = SECRET_KEY_FILE.read_text().strip()

# DEBUG = True solo en desarrollo
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps del proyecto
    "prestamos",
    "cuentas.apps.CuentasConfig",
    "auditoria",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # --- Middleware propio (requiere sesión, usuario y mensajes) ---
    "auditoria.middleware.SesionInactivaMiddleware",
    "auditoria.middleware.PrestamosVencidosMiddleware",
    "auditoria.middleware.AuditoriaMiddleware",
    "auditoria.middleware.AccesoNoAutorizadoMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------
# Las contraseñas se guardan hasheadas con PBKDF2-SHA256 (valor por defecto de Django)
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "prestamo_lista"
LOGOUT_REDIRECT_URL = "login"

# ---------------------------------------------------------------------------
# Sesiones: timeout de 30 minutos de inactividad
# ---------------------------------------------------------------------------
SESSION_INACTIVIDAD_SEGUNDOS = 30 * 60
SESSION_COOKIE_AGE = SESSION_INACTIVIDAD_SEGUNDOS  # duración de la cookie
SESSION_SAVE_EVERY_REQUEST = True                  # cada petición renueva el plazo
SESSION_EXPIRE_AT_BROWSER_CLOSE = False               # la cookie muestra su expiración (30 min)
SESSION_COOKIE_NAME = "prestamos_sesion"
SESSION_COOKIE_HTTPONLY = True                     # JavaScript no puede leer la cookie
SESSION_COOKIE_SAMESITE = "Lax"                    # mitiga CSRF entre sitios
SESSION_COOKIE_SECURE = not DEBUG                  # solo HTTPS en producción

# ---------------------------------------------------------------------------
# CSRF y cabeceras de seguridad
# ---------------------------------------------------------------------------
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

# ---------------------------------------------------------------------------
# Internacionalización
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Recordatorios por correo: se muestran en la consola (simulado)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "laboratorios-fis@uncp.edu.pe"

# ---------------------------------------------------------------------------
# Logging: auditoría en consola y en logs/auditoria.log
# ---------------------------------------------------------------------------
(BASE_DIR / "logs").mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "auditoria": {
            "format": "[{asctime}] {levelname:<7} {message}",
            "datefmt": "%d/%m/%Y %H:%M:%S",
            "style": "{",
        },
    },
    "handlers": {
        "consola": {"class": "logging.StreamHandler", "formatter": "auditoria"},
        "archivo": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "auditoria.log",
            "formatter": "auditoria",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "auditoria": {"handlers": ["consola", "archivo"], "level": "INFO", "propagate": False},
        # Los 403/404 ya los registra nuestro middleware: se evita el traceback duplicado
        "django.request": {"handlers": ["consola"], "level": "ERROR", "propagate": False},
    },
}
