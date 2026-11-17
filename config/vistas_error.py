"""Vistas de error propias. Las páginas 400, 403, 404 y 500 usan las vistas de Django con plantillas en español."""

from django.shortcuts import render


def fallo_csrf(request, reason=""):
    """
    Fallo de la protección CSRF (CSRF_FAILURE_VIEW). Se renderiza con la solicitud para que el menú muestre
    bien la sesión. El motivo técnico no se muestra al usuario: Django ya lo registra en el log.
    """
    return render(request, "403_csrf.html", status=403)
