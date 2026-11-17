"""
Configuración del proyecto · Sistema de votaciones del Festival de la Leyenda Vallenata.

Los valores sensibles (SECRET_KEY, DEBUG y credenciales de MySQL) se leen de variables
de entorno. En desarrollo se cargan desde el archivo .env, que nunca se sube a Git;
la plantilla con los nombres de las variables está en .env.example.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def variable_entorno(nombre, por_defecto=None):
    """Lee una variable de entorno; si falta o está vacía y no tiene valor por defecto, detiene el arranque."""
    valor = os.environ.get(nombre) or por_defecto
    if valor is None:
        raise ImproperlyConfigured(f"Falta la variable de entorno {nombre}. Revisa tu archivo .env (ver .env.example).")
    return valor


def lista_entorno(nombre, por_defecto=""):
    return [v.strip() for v in variable_entorno(nombre, por_defecto).split(",") if v.strip()]


def booleano_entorno(nombre, por_defecto="False"):
    return variable_entorno(nombre, por_defecto).lower() in ("1", "true", "si", "sí")


# ---------------------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------------------
SECRET_KEY = variable_entorno("DJANGO_SECRET_KEY")
DEBUG = booleano_entorno("DJANGO_DEBUG")
ALLOWED_HOSTS = lista_entorno("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Despliegue con HTTPS. Estas opciones vienen apagadas por defecto para poder probar con DEBUG=False en
# http://127.0.0.1 (con cookies seguras, el inicio de sesión no funcionaría sin HTTPS). La configuración de
# producción de ejemplo de .env.example las enciende, y con ella «check --deploy» no da advertencias.
SESSION_COOKIE_SECURE = booleano_entorno("DJANGO_COOKIES_SEGURAS")
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_SSL_REDIRECT = booleano_entorno("DJANGO_SECURE_SSL_REDIRECT")
SECURE_HSTS_SECONDS = int(variable_entorno("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = booleano_entorno("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS")
SECURE_HSTS_PRELOAD = booleano_entorno("DJANGO_SECURE_HSTS_PRELOAD")
CSRF_TRUSTED_ORIGINS = lista_entorno("DJANGO_CSRF_TRUSTED_ORIGINS", "")
# Solo si un proxy (Nginx, Apache, IIS…) termina el HTTPS y envía X-Forwarded-Proto
if booleano_entorno("DJANGO_DETRAS_DE_PROXY"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Siempre activas
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_FAILURE_VIEW = "config.vistas_error.fallo_csrf"


# ---------------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",  # runserver deja los estáticos a WhiteNoise, igual que en producción
    "django.contrib.staticfiles",
    # Aplicaciones del proyecto
    "cuentas",   # Usuario, registro, inicio y cierre de sesión (CU-01)
    "festival",  # Edición, Categoría, Votación y Opción; vistas públicas (CU-02, CU-04)
    "votos",     # Voto, registro del voto, «Mis votos» y RegistroAuditoria (CU-03, CU-06)
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # sirve los estáticos también con DEBUG=False
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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


# ---------------------------------------------------------------------------
# Base de datos: MySQL 8.0.11 o superior con el driver mysqlclient
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": variable_entorno("DB_NAME"),
        "USER": variable_entorno("DB_USER"),
        "PASSWORD": variable_entorno("DB_PASSWORD"),
        "HOST": variable_entorno("DB_HOST", "localhost"),
        "PORT": variable_entorno("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        # La base de pruebas (test_<DB_NAME>) también se crea en utf8mb4
        "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_0900_ai_ci"},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Autenticación: modelo de usuario propio desde la primera migración
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "cuentas.Usuario"

LOGIN_URL = "cuentas:login"
LOGIN_REDIRECT_URL = "festival:inicio"
LOGOUT_REDIRECT_URL = "festival:inicio"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ---------------------------------------------------------------------------
# Idioma, zona horaria y formato colombiano
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Archivos estáticos y subidos (foto opcional de las opciones)
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# En producción: «python manage.py collectstatic» copia aquí los estáticos y WhiteNoise los sirve.
# La carpeta se crea vacía si no existe, porque WhiteNoise avisa cuando falta (no se sube a Git).
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_ROOT.mkdir(exist_ok=True)
# WhiteNoise también los busca en sus carpetas de origen, así funcionan con DEBUG=False aunque
# no se haya ejecutado collectstatic (por ejemplo, para mostrar las páginas de error en la demostración).
WHITENOISE_USE_FINDERS = True

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


# ---------------------------------------------------------------------------
# Registro de errores: en consola y en logs/festival.log (rotativo, 1 MB × 5). La carpeta logs/ no se sube a Git.
# Solo guarda la ruta, el tipo de error y el traceback: ni correos, ni contraseñas, ni datos de los votos.
# ---------------------------------------------------------------------------
DIRECTORIO_LOGS = BASE_DIR / "logs"
DIRECTORIO_LOGS.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "consola": {"class": "logging.StreamHandler", "level": "ERROR", "formatter": "simple"},
        "archivo": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": DIRECTORIO_LOGS / "festival.log",
            "maxBytes": 1_000_000,
            "backupCount": 5,
            "encoding": "utf-8",
            "delay": True,
            "level": "WARNING",
            "formatter": "simple",
        },
    },
    "loggers": {
        # Errores 500, accesos denegados, fallos de CSRF y encabezados Host no permitidos
        "django.request": {"handlers": ["consola", "archivo"], "level": "WARNING", "propagate": False},
        "django.security": {"handlers": ["consola", "archivo"], "level": "WARNING", "propagate": False},
    },
}
