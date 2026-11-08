"""
Registro del voto (CU-03). Es el único lugar del sistema donde se crea un Voto.

registrar_voto valida en este orden:
1. Usuario autenticado y activo.
2. Categoría publicada, que admite voto del público y pertenece a la edición activa.
3. Votación abierta y dentro de su horario, según el reloj del servidor (RN-03).
4. Opción publicada, activa y perteneciente a una votación de esa categoría.
5. Que el usuario no haya votado ya en esa categoría y edición (RN-01).

La garantía final contra duplicados, incluso con solicitudes simultáneas, es la restricción única
«un_voto_por_usuario_categoria_edicion» de MySQL: si dos solicitudes pasan el paso 5 a la vez,
la segunda recibe IntegrityError al insertar y se responde «Ya votaste en esta categoría».
"""

import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from festival import reglas
from festival.models import Categoria, Opcion, Votacion
from festival.views import edicion_activa

from .models import RegistroAuditoria, Voto


class VotoRechazado(Exception):
    """Rechazo del voto con un mensaje para el usuario y el código HTTP que corresponde (400, 403 o 404)."""

    def __init__(self, mensaje, estado_http=403, auditar=""):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.estado_http = estado_http
        self.auditar = auditar  # acción que se registra en RegistroAuditoria; vacío = no se registra


def huella(valor):
    """HMAC-SHA256 con la SECRET_KEY: identifica sin guardar la IP o el navegador en claro."""
    return hmac.new(settings.SECRET_KEY.encode(), (valor or "").encode(), hashlib.sha256).hexdigest()


def votaciones_abiertas(categoria, ahora=None):
    """Votaciones de la categoría abiertas y dentro de su horario según el reloj del servidor (RN-03)."""
    ahora = ahora or timezone.now()
    return categoria.votaciones.filter(estado=Votacion.Estado.ABIERTA, abre_en__lte=ahora, cierra_en__gt=ahora)


def opciones_disponibles(categoria, ahora=None):
    """Opciones por las que se puede votar ahora en la categoría: publicadas, activas y de una votación abierta."""
    return (Opcion.objects
            .filter(votacion__in=votaciones_abiertas(categoria, ahora), publicada=True, estado=Opcion.Estado.ACTIVA)
            .select_related("votacion__categoria__edicion")
            .order_by("votacion__abre_en", "votacion__nombre", "orden", "nombre"))


def voto_en_categoria(usuario, categoria):
    """El voto del usuario en esa categoría y su edición, o None."""
    return (Voto.objects.filter(usuario=usuario, categoria=categoria, edicion_id=categoria.edicion_id)
            .select_related("opcion", "votacion", "categoria", "edicion").first())


def verificar_categoria(categoria, ahora=None):
    """Pasos 2 y 3 para una categoría publicada: lanza VotoRechazado si hoy no se puede votar en ella.
    Lo usan el servicio y las páginas, para que ambos apliquen la misma regla."""
    activa = edicion_activa()
    if not categoria.admite_voto_publico or activa is None or categoria.edicion_id != activa.pk:
        raise VotoRechazado("Esta categoría no está habilitada para el voto del público.", 403,
                            auditar="Voto rechazado: categoría no habilitada")
    if not votaciones_abiertas(categoria, ahora).exists():
        raise VotoRechazado("Esta categoría no tiene votaciones abiertas en este momento.", 403,
                            auditar="Voto rechazado: votación cerrada o fuera de horario")


def se_puede_votar(categoria):
    """Versión sin excepción de verificar_categoria, para las plantillas."""
    try:
        verificar_categoria(categoria)
    except VotoRechazado:
        return False
    return True


def auditar(usuario, accion, entidad, detalle="", ip=""):
    usuario = usuario if getattr(usuario, "is_authenticated", False) else None
    RegistroAuditoria.objects.create(usuario=usuario, accion=accion[:100], entidad_afectada=entidad[:100],
                                     detalle=detalle, huella_ip=huella(ip) if ip else "")


def registrar_voto(usuario, categoria_id, opcion_id, *, ip="", navegador=""):
    """Registra el voto o lanza VotoRechazado. categoria_id viene de la URL y opcion_id del formulario."""
    try:
        with transaction.atomic():
            return _validar_y_guardar(usuario, categoria_id, opcion_id, ip, navegador)
    except VotoRechazado as rechazo:
        # Fuera de la transacción: el registro de auditoría no se deshace junto con el voto rechazado.
        if rechazo.auditar:
            auditar(usuario, rechazo.auditar, f"festival.Categoria #{categoria_id}",
                    f"{rechazo.mensaje} Opción enviada: {opcion_id!r}.", ip)
        raise
    except IntegrityError:
        # La restricción única detuvo un segundo voto, por ejemplo de dos solicitudes simultáneas.
        if not Voto.objects.filter(usuario=usuario, categoria_id=categoria_id).exists():
            raise
        auditar(usuario, "Voto duplicado detenido por la base de datos", f"festival.Categoria #{categoria_id}",
                f"Opción enviada: {opcion_id!r}.", ip)
        raise VotoRechazado("Ya votaste en esta categoría.", 403) from None


def _validar_y_guardar(usuario, categoria_id, opcion_id, ip, navegador):
    # 1. Usuario autenticado y activo
    if not getattr(usuario, "is_authenticated", False) or not usuario.is_active:
        raise VotoRechazado("Debes iniciar sesión con una cuenta activa para votar.", 403)
    # PENDIENTE (RN-04, P-01): mientras REQUIERE_CORREO_VERIFICADO sea False, este paso no rechaza a nadie.
    if reglas.REQUIERE_CORREO_VERIFICADO and not usuario.correo_verificado:
        raise VotoRechazado("Debes verificar tu correo antes de votar.", 403)

    # 2. Categoría publicada, que admite voto del público y pertenece a la edición activa
    categoria = Categoria.objects.select_related("edicion").filter(pk=categoria_id, publicada=True).first()
    if categoria is None:
        raise VotoRechazado("Esta categoría no existe o no está publicada.", 404)
    # 2 (resto) y 3. Admite voto del público, es de la edición activa y tiene una votación abierta
    # dentro de su horario según el reloj del servidor (RN-03)
    ahora = timezone.now()
    verificar_categoria(categoria, ahora)

    # 4. Opción publicada, activa y de una votación abierta de esa categoría
    try:
        opcion_id = int(opcion_id)
    except (TypeError, ValueError):
        raise VotoRechazado("Elige una opción válida.", 400) from None
    opcion = opciones_disponibles(categoria, ahora).filter(pk=opcion_id).first()
    if opcion is None:
        if Opcion.objects.filter(pk=opcion_id).exclude(votacion__categoria=categoria).exists():
            raise VotoRechazado("La opción elegida no corresponde a esta categoría.", 400,
                                auditar="Voto rechazado: opción de otra categoría")
        raise VotoRechazado("La opción elegida no está disponible para votar.", 400,
                            auditar="Voto rechazado: opción no disponible")

    # 5. RN-01: un voto por usuario, categoría y edición
    if Voto.objects.filter(usuario=usuario, categoria=categoria, edicion_id=categoria.edicion_id).exists():
        raise VotoRechazado("Ya votaste en esta categoría.", 403, auditar="Voto rechazado: ya votó en la categoría")

    # Registro: votación, categoría y edición se toman de la opción, nunca del formulario
    semilla = f"{usuario.pk}|{opcion.pk}|{opcion.votacion_id}|{categoria.pk}|{categoria.edicion_id}|{ahora.isoformat()}|{secrets.token_hex(16)}"
    voto = Voto.desde_opcion(usuario, opcion, huella_ip=huella(ip), huella_navegador=huella(navegador),
                             hash_auditoria=hashlib.sha256(semilla.encode()).hexdigest())
    voto.full_clean(validate_constraints=False)  # la restricción única la aplica MySQL al insertar
    voto.save()
    return voto
