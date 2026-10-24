from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm
from django.utils import timezone

from festival import reglas

from .models import Usuario

# Versión de la política de tratamiento de datos que acepta quien se registra (Ley 1581 de 2012).
# Si el texto de la política cambia, se actualiza este valor.
VERSION_POLITICA_DATOS = "1.0"


def _estilo_campos(formulario):
    """Aplica las clases del prototipo a los campos de texto."""
    for campo in formulario.fields.values():
        if not isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs.setdefault("class", "input")


class RegistroForm(BaseUserCreationForm):
    """CU-01 · Registro: correo, nombre para mostrar, contraseña dos veces y dos casillas separadas. No pide celular (P-01)."""

    autoriza_datos = forms.BooleanField(
        label="Autorizo el tratamiento de mis datos personales (Ley 1581 de 2012, Habeas Data).",
        error_messages={"required": "Debes autorizar el tratamiento de tus datos para crear la cuenta."},
    )
    # RN-08, pendiente (P-12): la edad mínima es un valor provisional de festival/reglas.py.
    mayor_edad = forms.BooleanField(
        label=f"Declaro que soy mayor de {reglas.EDAD_MINIMA} años.",
        help_text="Edad mínima provisional, pendiente de la decisión de la Fundación (P-12).",
        error_messages={"required": "Debes declarar que cumples la edad mínima."},
    )

    class Meta:
        model = Usuario
        fields = ("email", "nombre_para_mostrar")
        widgets = {
            "email": forms.EmailInput(attrs={"autocomplete": "email", "inputmode": "email", "placeholder": "nombre@correo.com"}),
            "nombre_para_mostrar": forms.TextInput(attrs={"autocomplete": "nickname"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilo_campos(self)

    def clean_email(self):
        correo = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=correo).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo.")
        return correo

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.autorizacion_datos_en = timezone.now()
        usuario.politica_datos_version = VERSION_POLITICA_DATOS
        usuario.declara_mayor_edad = True
        # PENDIENTE (RN-04, P-01): aquí iría el envío del correo de verificación. Mientras la regla
        # esté pendiente (reglas.REQUIERE_CORREO_VERIFICADO = False), correo_verificado queda en False
        # y no impide iniciar sesión.
        if commit:
            usuario.save()
        return usuario


class IngresoForm(AuthenticationForm):
    """CU-01 · Inicio de sesión con correo y contraseña."""

    error_messages = {
        "invalid_login": "El correo o la contraseña no coinciden.",
        "inactive": "Esta cuenta está desactivada.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilo_campos(self)
        self.fields["username"].widget.attrs.update({"autocomplete": "email", "inputmode": "email"})
