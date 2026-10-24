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


# ---------------------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------------------
SECRET_KEY = variable_entorno("DJANGO_SECRET_KEY")
DEBUG = variable_entorno("DJANGO_DEBUG", "False").lower() in ("1", "true", "si", "sí")
ALLOWED_HOSTS = lista_entorno("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")


# ---------------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Aplicaciones del proyecto
    "cuentas",   # Usuario, registro, inicio y cierre de sesión (CU-01)
    "festival",  # Edición, Categoría, Votación y Opción; vistas públicas (CU-02, CU-04)
    "votos",     # Voto y RegistroAuditoria: solo estructura en esta entrega (CU-03, CU-06)
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
