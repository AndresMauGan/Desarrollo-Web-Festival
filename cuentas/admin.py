from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from .models import Usuario


class UsuarioCreationForm(BaseUserCreationForm):
    class Meta:
        model = Usuario
        fields = ("email", "nombre_para_mostrar")


class UsuarioChangeForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = "__all__"


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = UsuarioChangeForm
    add_form = UsuarioCreationForm

    list_display = ("email", "nombre_para_mostrar", "is_staff", "is_active", "correo_verificado", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active", "correo_verificado", "declara_mayor_edad")
    search_fields = ("email", "nombre_para_mostrar")
    ordering = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("nombre_para_mostrar", "correo_verificado")}),
        ("Autorización de datos y edad", {"fields": ("autorizacion_datos_en", "politica_datos_version", "declara_mayor_edad")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "nombre_para_mostrar", "password1", "password2"),
        }),
    )
    readonly_fields = ("last_login", "date_joined")
