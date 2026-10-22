from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UsuarioManager(BaseUserManager):
    """Crea usuarios identificados por correo (el modelo no tiene nombre de usuario)."""

    use_in_migrations = True

    def _crear(self, email, password, **campos):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")
        usuario = self.model(email=self.normalize_email(email), **campos)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **campos):
        campos.setdefault("is_staff", False)
        campos.setdefault("is_superuser", False)
        return self._crear(email, password, **campos)

    def create_superuser(self, email, password=None, **campos):
        campos.setdefault("is_staff", True)
        campos.setdefault("is_superuser", True)
        if campos["is_staff"] is not True or campos["is_superuser"] is not True:
            raise ValueError("Un superusuario debe tener is_staff=True e is_superuser=True.")
        return self._crear(email, password, **campos)


class Usuario(AbstractUser):
    """
    Cuenta del sistema (Entrega 1: entidad Usuario).

    - Se identifica con el correo, que es único; no hay nombre de usuario.
    - El nombre visible es «nombre para mostrar»; por eso se quitan nombre y apellido de AbstractUser.
    - La contraseña cifrada, «activo» (is_active) y «personal» (is_staff) vienen de AbstractUser.
    - El personal administra desde Django Admin y no vota (RN-08, pendiente).

    Relaciones (las define el lado «muchos», en la aplicación votos):
    - Usuario emite Voto: 1 a 0..*, related_name «votos».
    - Usuario genera Registro de auditoría: 0..1 a 0..*, related_name «registros».
    """

    username = None
    first_name = None
    last_name = None

    email = models.EmailField("correo electrónico", unique=True)
    nombre_para_mostrar = models.CharField("nombre para mostrar", max_length=60)
    # PENDIENTE (RN-04, P-01): el método de verificación no está decidido. Este campo solo
    # guarda el dato; no bloquea el inicio de sesión mientras la regla siga pendiente.
    correo_verificado = models.BooleanField(
        "correo verificado",
        default=False,
        help_text="Pendiente de validación (P-01): por ahora no impide iniciar sesión.",
    )
    # Ley 1581 de 2012 (Habeas Data): cuándo autorizó y qué versión de la política aceptó.
    autorizacion_datos_en = models.DateTimeField("autorización de datos (fecha)", null=True, blank=True)
    politica_datos_version = models.CharField("versión de la política de datos", max_length=20, blank=True)
    # PENDIENTE (RN-08, P-12): la edad mínima es provisional; se guarda la declaración, no la edad.
    declara_mayor_edad = models.BooleanField("declara ser mayor de edad", default=False)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["nombre_para_mostrar"]

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["email"]

    def __str__(self):
        return f"{self.nombre_para_mostrar} <{self.email}>" if self.nombre_para_mostrar else self.email

    def get_full_name(self):
        return self.nombre_para_mostrar or self.email

    def get_short_name(self):
        return self.nombre_para_mostrar or self.email
