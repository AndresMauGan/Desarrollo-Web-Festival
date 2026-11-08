from django import forms

from festival.models import Opcion

from .servicios import opciones_disponibles


class ElegirOpcionForm(forms.Form):
    """Paso «elegir»: el campo opción solo acepta las opciones por las que hoy se puede votar en esa categoría."""

    opcion = forms.ModelChoiceField(
        queryset=Opcion.objects.none(),
        widget=forms.RadioSelect,
        error_messages={
            "required": "Elige una opción para continuar.",
            "invalid_choice": "La opción elegida no es válida para esta categoría.",
        },
    )

    def __init__(self, *args, categoria, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["opcion"].queryset = opciones_disponibles(categoria)
