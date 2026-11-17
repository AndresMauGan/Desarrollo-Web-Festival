# Sistema de votaciones · Festival de la Leyenda Vallenata

Proyecto universitario de Desarrollo Web (Fundación Universitaria del Área Andina).

Aplicación web en **Django 5.2 (patrón MVT) + MySQL 8** para el voto del público en el Festival. Las personas se registran, eligen una categoría, seleccionan una opción, confirman y el voto queda guardado en MySQL. Cada persona puede votar **una sola vez por categoría y edición**, aunque la categoría tenga varias votaciones (subeventos) abiertas.

Qué incluye:
- **Consulta pública:** ediciones, categorías, votaciones y opciones desde MySQL.
- **Votación con sesión iniciada:** elegir, confirmar y recibir un comprobante.
- **Validaciones en el servidor:** categorías cerradas o no habilitadas, opciones que no corresponden, solicitudes sin sesión y votos duplicados, incluidas las solicitudes simultáneas.
- **«Mis votos»:** cada persona ve las categorías en las que votó.
- **Resultados:** conteos reales para el personal y resultados públicos según la visibilidad que elija el administrador.
- **Administración dinámica:** una edición nueva (por ejemplo, 2028) se configura desde el admin, sin tocar el código.
- **Perfiles:** superusuario, administración del festival y votante, cada uno con sus permisos.
- **API de consulta:** `GET /api/categorias/` devuelve en JSON las categorías y sus opciones.
- **Listo para desplegar:** configuración de seguridad, páginas de error en español, registro de errores, respaldos e integración continua.

## Tecnologías

| Tecnología | Versión |
|---|---|
| Python | 3.11 o superior (probado con 3.11.2) |
| Django | 5.2.18 (LTS) |
| MySQL Server | 8.0.11 o superior (probado con 8.0.33), utf8mb4 |
| mysqlclient | 2.3.0 |
| Pillow | 12.3.0 (fotos opcionales de las opciones) |
| python-dotenv | 1.2.4 (lee el archivo `.env`) |
| WhiteNoise | 6.9.0 (sirve los archivos estáticos también con `DEBUG=False`) |

Las dependencias están en [`requirements.txt`](requirements.txt). La configuración usa idioma `es-co`, zona horaria `America/Bogota` y `USE_TZ = True`.

## 1. Clonar e instalar las dependencias

Necesitas Python, MySQL Server (en Windows sirve MySQL Installer, que incluye MySQL Workbench) y Git.

```bash
git clone https://github.com/AndresMauGan/Desarrollo-Web.git
cd Desarrollo-Web
python -m venv .venv
```

Activa el entorno virtual:

| Terminal | Comando |
|---|---|
| PowerShell | `.venv\Scripts\Activate.ps1` |
| Git Bash | `source .venv/Scripts/activate` |
| Linux o macOS | `source .venv/bin/activate` |

Instala las dependencias (vuelve a hacerlo cada vez que cambie `requirements.txt`):

```bash
pip install -r requirements.txt
```

En Windows, `mysqlclient` se instala sin compilar. En Linux hace falta antes `sudo apt install pkg-config libmysqlclient-dev`, y en macOS `brew install mysql-client pkg-config`.

## 2. Crear las bases de datos y el usuario de MySQL

1. Inicia el servidor de MySQL. En Windows: aplicación **Servicios** → `MySQL80` → Iniciar, o `net start MySQL80` en una terminal de administrador.
2. Abre MySQL Workbench (o el cliente `mysql`) con tu cuenta `root` y ejecuta lo siguiente. Cambia `<contraseña>` por una clave tuya; no la escribas en ningún archivo del repositorio.

```sql
-- Base real y base de demostración (ver «Base real y base de demostración»)
CREATE DATABASE festival_votaciones CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE festival_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'festival_app'@'localhost' IDENTIFIED BY '<contraseña>';
GRANT ALL PRIVILEGES ON festival_votaciones.* TO 'festival_app'@'localhost';
GRANT ALL PRIVILEGES ON festival_demo.* TO 'festival_app'@'localhost';
-- Bases temporales que crean «manage.py test» y «probar_concurrencia» (test_<DB_NAME>)
GRANT ALL PRIVILEGES ON test_festival_votaciones.* TO 'festival_app'@'localhost';
GRANT ALL PRIVILEGES ON test_festival_demo.* TO 'festival_app'@'localhost';
FLUSH PRIVILEGES;
```

Si ya tenías el usuario de las entregas anteriores, ejecuta solo las líneas de `festival_demo` y `test_festival_demo`.

## 3. Configurar las variables de entorno

Copia la plantilla y complétala. El archivo `.env` queda fuera de Git: **nunca subas contraseñas ni claves al repositorio**.

```bash
cp .env.example .env
```

| Variable | Valor |
|---|---|
| `DJANGO_SECRET_KEY` | Genérala con `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DJANGO_DEBUG` | `True` solo en desarrollo |
| `DB_NAME` | `festival_votaciones` (real) o `festival_demo` (demostración) |
| `DB_USER`, `DB_PASSWORD` | `festival_app` y la contraseña del paso 2 |
| `DB_HOST`, `DB_PORT` | `localhost` y `3306` |

Si falta una variable, Django se detiene con un mensaje que dice cuál. Al final de `.env.example` está, comentada, la configuración de producción de ejemplo (ver «Despliegue»).

## 4. Migraciones, grupos y administrador

```bash
python manage.py migrate
python manage.py crear_grupos
python manage.py createsuperuser
```

- **`migrate`** crea las tablas. Las migraciones de la entrega final son:
  - [`festival/migrations/0003_votacion_resultados_publicados.py`](festival/migrations/0003_votacion_resultados_publicados.py): campo «resultados publicados» para la visibilidad «En la ceremonia».
  - [`votos/migrations/0003_permiso_ver_resultados.py`](votos/migrations/0003_permiso_ver_resultados.py): permiso `votos.ver_resultados`.
- **`crear_grupos`** crea el grupo «Administración del festival» con sus permisos. Se puede ejecutar varias veces.
- **`createsuperuser`** pide correo, nombre para mostrar y contraseña. Las cuentas se identifican con el correo.

Los datos de prueba solo van en la base de demostración: ver la siguiente sección.

## 5. Base real y base de demostración

Hay dos bases, y se elige una con `DB_NAME` en `.env`. Para cambiar de base, edita `.env` y reinicia el servidor.

| Base | Para qué | Cómo se llena |
|---|---|---|
| `festival_votaciones` | **Real.** Solo lo que configure el administrador. | Desde el admin, sin datos de prueba. |
| `festival_demo` | **Demostración y ensayos.** | `python manage.py preparar_demo` (o `cargar_datos_prueba`). |

Los comandos de datos de prueba protegen la base real:
- **`cargar_datos_prueba`:**
  - muestra el nombre de la base en la que va a escribir y pide confirmación;
  - avisa si esa base no es la de demostración;
  - con `DJANGO_DEBUG=False` se niega a ejecutarse, salvo con `--permitir-sin-debug`.
- **`preparar_demo`:** solo funciona si `DB_NAME` termina en `_demo`.
- **`probar_concurrencia`:** trabaja en una base temporal propia, así que no deja datos ni en la real ni en la de demostración.

**Si tu base real tiene datos de prueba de entregas anteriores**, respáldala y vuélvela a crear vacía:

1. Respáldala con `python manage.py respaldar_base`, con `DB_NAME=festival_votaciones`.
2. Como `root`, ejecuta:
   ```sql
   DROP DATABASE festival_votaciones;
   CREATE DATABASE festival_votaciones CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
   ```
3. Ejecuta otra vez los comandos de la sección 4.

## 6. Ejecutar el proyecto

```bash
python manage.py runserver
```

| Página | Dirección |
|---|---|
| Sitio público | http://127.0.0.1:8000/ |
| Categorías de la edición activa | http://127.0.0.1:8000/categorias/ |
| Registro e inicio de sesión | http://127.0.0.1:8000/cuentas/registro/ · http://127.0.0.1:8000/cuentas/ingresar/ |
| Mis votos | http://127.0.0.1:8000/votar/mis-votos/ |
| Resultados (personal) | http://127.0.0.1:8000/resultados/ |
| Resultados públicos de una votación | http://127.0.0.1:8000/votaciones/&lt;id&gt;/resultados/ |
| API | http://127.0.0.1:8000/api/categorias/ |
| Administración | http://127.0.0.1:8000/admin/ |

## 7. Cómo votar

1. **Crea una cuenta** en *Registrarse* (`/cuentas/registro/`) o inicia sesión. Sin sesión, al intentar votar el sitio te lleva al inicio de sesión y después te devuelve a la categoría.
2. **Elige una categoría** con una votación *En vivo* y pulsa **Votar en esta categoría** (`/votar/categoria/<id>/`).
3. **Selecciona una opción.** Si la categoría tiene varios subeventos abiertos, se muestran todos, pero solo puedes elegir una opción entre ellos. Pulsa **Continuar**.
4. **Confirma.** La pantalla de confirmación advierte que el voto es irreversible. Pulsa **Confirmar voto**.
5. **Recibe el comprobante,** con un código como `VV-1A2B-3C4D`, la fecha y la hora. Lo puedes volver a ver en **Mis votos**.

Si vuelves a la categoría después de votar, verás tu voto y el comprobante en lugar del formulario. Puedes votar en las demás categorías abiertas.

## 8. Resultados y su visibilidad

**Para el personal:** la página `/resultados/` ([`votos/views.py`](votos/views.py), `ResultadosView`).
- **Acceso:** exige el permiso `votos.ver_resultados`. Sin sesión lleva al inicio de sesión; un votante recibe un 403.
- **Edición:** muestra la activa, u otra con `?edicion=<año>`.
- **Contenido:**
  - **por categoría,** cuántas personas votaron;
  - **por votación,** su estado, si el público ya puede ver los resultados y, por cada opción, votos, porcentaje y una barra, de mayor a menor;
  - **la hora de la consulta.**
  - Las opciones con 0 votos también aparecen.
- **Cálculo** ([`votos/resultados.py`](votos/resultados.py)):
  - Usa agregaciones del ORM con `Count`: son tres consultas para toda la edición, sin importar cuántas opciones haya.
  - No usa funciones de fecha de MySQL, que fallan sin las tablas de zonas horarias.

**Para el público:** `/votaciones/<id>/resultados/`, enlazada desde el detalle de cada votación. Lo que se ve depende de la visibilidad que elige el administrador en cada votación. Es una regla provisional (RN-06, pendiente P-05):

| Visibilidad | El público ve los resultados… |
|---|---|
| En vivo | siempre |
| Al cierre | solo cuando la votación está **cerrada** |
| En la ceremonia | solo cuando el personal marca **resultados publicados** |

- **Mientras no se puedan ver,** la página explica cuándo se publicarán y no muestra ningún número.
- **En el admin de Votación:** las acciones «Publicar resultados» y «Retirar la publicación» marcan o desmarcan el campo, y dejan registro en la auditoría.
- **Columna «votos»:** las listas del admin de Votación y de Opción la muestran, de solo lectura.
- **La API no cambia:** sigue sin conteos.

## 9. Perfiles y permisos

| Perfil | Cómo se crea | Qué puede hacer |
|---|---|---|
| **Superusuario** (técnico) | `python manage.py createsuperuser` | Todo, incluida la gestión de usuarios y grupos. |
| **Administración del festival** | La persona se registra en el sitio y luego `python manage.py crear_grupos --asignar <correo>`. También se puede marcar «Es staff» y agregar el grupo desde el admin. | Agregar, cambiar y ver ediciones, categorías, votaciones y opciones; ver votos y auditoría; ver resultados. **No** gestiona usuarios ni borra nada. |
| **Votante** | Se registra en `/cuentas/registro/`. | Votar, ver su comprobante y «Mis votos». |

- **Menú según el perfil:** «Administración» y «Resultados» solo aparecen para quien tiene permiso; «Mis votos» y «Cerrar sesión», para quien inició sesión.
- **Accesos sin permiso:**
  - un votante que entra a `/admin/` ve el inicio de sesión del admin con el aviso «no está autorizado»;
  - en `/resultados/`, recibe un 403 en español;
  - sin sesión, las páginas protegidas llevan al inicio de sesión con `next`.
- **Contraseñas:** Django las guarda con su hasher (PBKDF2 con SHA-256 y sal), nunca en claro.
- **Grupo:** los permisos están en [`cuentas/grupos.py`](cuentas/grupos.py).
- **RN-08 sigue pendiente:** si el personal puede votar (P-12). Por ahora el sistema no lo impide.

## 10. Cómo configurar una nueva edición (por ejemplo, 2028)

Todo se hace desde el admin, sin tocar el código. Lo comprueba la prueba `test_festival_2028_sin_tocar_el_codigo` de [`festival/test_admin_dinamico.py`](festival/test_admin_dinamico.py).

**Opción rápida: duplicar la edición anterior**
1. **Duplica la edición anterior.** En **Administración → Ediciones**, marca la edición 2027 y elige la acción **«Duplicar la edición»**. Revisa los datos sugeridos (año 2028, número 61, nombre y fechas) y pulsa **Crear la edición**.
   - Se crean una edición inactiva, sus categorías sin publicar y sus votaciones en borrador, con el horario corrido según la nueva fecha de inicio.
   - No se copian opciones, votos ni auditoría.
2. **Completa las votaciones.** En **Votaciones**, abre cada votación de 2028, revisa el horario y agrega al menos dos opciones publicadas (RN-11).
3. **Ábrelas.** Márcalas en la lista y elige **«Abrir las votaciones elegidas»**.
   - Si una no cumple RN-11, el admin la deja como estaba y dice por qué.
   - Si su horario aún no empieza, también avisa.
4. **Publica las categorías y activa la edición.** En **Ediciones → 2028**, marca «publicada» en las categorías, marca **«activa»** y guarda.
   - Solo puede haber una edición activa: el admin desactiva la anterior y lo explica en un mensaje.

**Desde cero:** en **Ediciones → Añadir**, llena los datos y sus categorías. Luego, en **Votaciones → Añadir**, elige la categoría, el horario y sus opciones, y sigue desde el paso 3.

**Para comprobarlo,** el inicio, las categorías, la página de votación y `GET /api/categorias/` muestran 2028.

**Acciones de estado de una votación** (cada una deja registro en la auditoría):
- **Abrir:** desde borrador, programada o pausada.
- **Pausar:** desde abierta.
- **Cerrar:** desde programada, abierta o pausada.

## 11. API de consulta: `GET /api/categorias/`

- **Código:** [`festival/api.py`](festival/api.py); la ruta está en [`festival/urls.py`](festival/urls.py).
- **Edición:** devuelve las categorías publicadas de la edición activa, o de otra con `?edicion=<año>`, por ejemplo `/api/categorias/?edicion=2026`.
- **Contenido:** cada categoría trae su edición, sus votaciones (id, nombre, estado y horario) y sus opciones publicadas y activas (id, nombre, tipo y descripción).
- **Lo que no incluye:** conteos de votos (RN-06) ni datos personales.
- **Métodos:** solo acepta GET. POST, PUT o DELETE responden **405**.
- **Errores:** `?edicion` inexistente responde 404 y no numérica responde 400.

Ejemplo, recortado a una categoría, una votación y una opción:

```json
{
  "edicion": {"anio": 2027, "numero": 60, "nombre": "60.º Festival de la Leyenda Vallenata",
              "fecha_inicio": "2027-04-28", "fecha_fin": "2027-05-01", "activa": true},
  "categorias": [
    {
      "id": 6, "nombre": "Acordeonera Mayor", "familia": "acordeon", "nivel": "Mayor", "admite_voto_publico": true,
      "edicion": {"anio": 2027, "nombre": "60.º Festival de la Leyenda Vallenata"},
      "votaciones": [
        {
          "id": 4, "nombre": "Semifinal Acordeonera Mayor", "ronda": "semifinal",
          "estado": "abierta", "estado_publico": "En vivo",
          "abre_en": "2026-11-07T18:15:30.888787-05:00", "cierra_en": "2026-12-07T19:15:30.888787-05:00",
          "opciones": [{"id": 7, "nombre": "Acordeonera Ficticia Uno", "tipo": "persona", "descripcion": ""}]
        }
      ]
    }
  ]
}
```

## 12. Dónde se controla la unicidad (un voto por usuario, categoría y edición)

La regla RN-01 la fija la guía de la Entrega 3. Se aplica en tres capas:

1. **En MySQL, que es la garantía final.**
   - **Dónde:** [`votos/models.py`](votos/models.py) declara en `Voto.Meta.constraints` la restricción `UniqueConstraint(fields=["usuario", "categoria", "edicion"], name="un_voto_por_usuario_categoria_edicion")`.
   - **Cómo llega a la base:** la migración [`votos/migrations/0002_voto_categoria_edicion_unicidad.py`](votos/migrations/0002_voto_categoria_edicion_unicidad.py) la crea como índice único de la tabla `votos_voto`.
   - **Cómo verlo en MySQL:** `SHOW INDEX FROM votos_voto WHERE Key_name = 'un_voto_por_usuario_categoria_edicion';`
2. **En el servicio `registrar_voto`, en [`votos/servicios.py`](votos/servicios.py).** Es el único lugar donde se crea un voto.
   - Valida en orden, dentro de `transaction.atomic()`: sesión activa, categoría habilitada, votación abierta y en horario, opción válida de esa categoría y que no exista ya un voto en la categoría.
   - Si dos solicitudes simultáneas pasan esas validaciones a la vez, MySQL rechaza la segunda con `IntegrityError`. El servicio la captura y responde «Ya votaste en esta categoría», sin error 500.
3. **En el modelo.** La votación, la categoría y la edición del voto se toman siempre de la opción elegida (`Voto.desde_opcion`), nunca del formulario. Por eso no se puede esquivar la regla enviando otra categoría.

Las vistas ([`votos/views.py`](votos/views.py)) solo muestran el resultado. Si ya votaste, no aparece el formulario. Cada rechazo responde con su código HTTP (400, 403 o 404), un mensaje en español y, en los casos importantes, un registro de auditoría.

## 13. Pruebas

```bash
python manage.py test                          # todas las pruebas (143)
python manage.py test votos.test_casos_prueba  # solo los casos CP-01 a CP-10
```

Django crea y borra la base `test_<DB_NAME>`; por eso el usuario de MySQL necesita los permisos del paso 2. Las contraseñas de las pruebas se generan en memoria en cada ejecución.

| Archivo | Qué prueba |
|---|---|
| [`votos/test_casos_prueba.py`](votos/test_casos_prueba.py) | Casos CP-01 a CP-10 de la guía (tabla abajo) |
| [`votos/test_resultados.py`](votos/test_resultados.py) | Resultados: conteos frente a `SELECT opcion_id, COUNT(*) … GROUP BY opcion_id`, opciones con 0 votos, permisos y visibilidad pública |
| [`festival/test_admin_dinamico.py`](festival/test_admin_dinamico.py) | Una sola edición activa, acciones de votación, duplicar edición, validaciones y «Festival 2028 sin tocar el código» |
| [`cuentas/test_permisos.py`](cuentas/test_permisos.py) | Perfiles y menú, accesos sin permiso, páginas de error y `check --deploy` |
| [`festival/test_comandos.py`](festival/test_comandos.py), [`votos/test_comandos.py`](votos/test_comandos.py) | `respaldar_base`, `preparar_demo` y `probar_concurrencia` |
| `cuentas/tests.py`, `festival/tests.py`, `votos/tests.py` | Modelos, registro e inicio de sesión, vistas públicas, admin y datos de prueba (entregas 2 y 3) |

| Caso | Prueba | Qué comprueba |
|---|---|---|
| CP-01 | `test_cp01_voto_valido` | Elegir, confirmar y que quede la fila en `votos_voto` |
| CP-02 | `test_cp02_segundo_voto_en_la_misma_categoria_se_rechaza` | Rechaza la misma opción, otra opción y otro subevento |
| CP-03 | `test_cp03_voto_en_otra_categoria_se_permite` | Permite votar en otra categoría |
| CP-04 | `test_cp04_sin_sesion_se_exige_iniciar_sesion` | Sin sesión, redirige al inicio de sesión con `next` |
| CP-05 | `test_cp05_categoria_no_habilitada_se_rechaza` | Sin voto del público, otra edición, cerrada, pausada, fuera de horario, sin publicar |
| CP-06 | `test_cp06_opcion_de_otra_categoria_se_rechaza` | Opción de otra categoría, sin publicar, inexistente o vacía |
| CP-07 | `test_cp07_mis_votos_muestra_solo_los_registros_propios` | «Mis votos» muestra solo los votos propios |
| CP-08 | `test_cp08_el_admin_muestra_los_votos_igual_que_mysql` | El admin coincide con `SELECT … FROM votos_voto`, también con filtros |
| CP-09 | `test_cp09_dos_solicitudes_simultaneas_dejan_un_solo_voto` y `test_cp09_la_restriccion_de_mysql_detiene_el_duplicado` | Dos hilos a la vez contra MySQL: queda un voto |
| CP-10 | `test_cp10_api_categorias_devuelve_json_con_datos_reales` | JSON válido con los datos de MySQL; POST responde 405 |

### Demostración de concurrencia fuera de las pruebas

```bash
python manage.py probar_concurrencia                               # 2 solicitudes simultáneas
python manage.py probar_concurrencia --solicitudes 8 --forzar-carrera
python manage.py probar_concurrencia --solicitudes 8 --forzar-carrera --conservar
```

- **Qué hace:**
  - crea una base temporal `test_<DB_NAME>`, igual que `manage.py test`, y le carga los datos de prueba;
  - envía varias solicitudes de voto a la vez a la misma categoría, cada una en su propio hilo y con su propia conexión a MySQL.
- **Qué muestra:** cuántas se registraron, cuántas rechazó Django y cuántas detuvo la restricción de MySQL. Al final cuenta los votos con SQL directo; siempre debe quedar uno.
- **`--forzar-carrera`:** todas las solicitudes pasan las validaciones de Django antes de que alguna inserte, así que solo MySQL puede detener los duplicados.
- **Al terminar elimina la base temporal:** no queda ningún dato en tu base.
- **`--conservar`:** deja la base temporal para revisarla en MySQL Workbench con el `SELECT` que imprime. Se reemplaza la próxima vez que corras el comando o las pruebas.

## 14. Preparación de la demostración

Antes del turno, con `DB_NAME=festival_demo` en `.env`:

```bash
python manage.py migrate
python manage.py preparar_demo
```

`preparar_demo`:
1. verifica que no falten migraciones;
2. recarga los datos de prueba con horarios vigentes;
3. crea el grupo «Administración del festival»;
4. imprime un resumen: votaciones abiertas, el id de cada categoría, los votos ya registrados y qué perfiles faltan.

No crea usuarios. Crea los que falten así:
- **Superusuario:** `python manage.py createsuperuser`.
- **Administración del festival:** regístrala en el sitio y luego ejecuta `python manage.py crear_grupos --asignar <correo>`.
- **Votante:** regístrala en el sitio.

**Para empezar con 0 votos:** los votos de los ensayos no se borran (RN-02). Vuelve a crear la base de demostración (como `root` o con `festival_app`) y repite los pasos:
```sql
DROP DATABASE festival_demo;
CREATE DATABASE festival_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

**Para mostrar las páginas de error en vivo,** usa `DJANGO_DEBUG=False` en `.env` y reinicia el servidor. WhiteNoise sigue sirviendo el CSS.

## 15. Despliegue

La aplicación no está publicada, pero está lista para hacerlo.

**Configuración de producción de ejemplo:**
- Está comentada al final de [`.env.example`](.env.example) y no lleva valores reales.
- Con ella, `python manage.py check --deploy` no da advertencias. Lo comprueba la prueba `DespliegueTests` de [`cuentas/test_permisos.py`](cuentas/test_permisos.py).
- Las opciones de HTTPS vienen apagadas por defecto: así se puede probar con `DEBUG=False` en `http://127.0.0.1`.

**Lista de verificación:**
- [ ] `DJANGO_DEBUG=False`.
- [ ] `DJANGO_SECRET_KEY` nueva, generada solo para el servidor.
- [ ] `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS` con el dominio real.
- [ ] **HTTPS** con un certificado válido.
  - Activa `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_COOKIES_SEGURAS` y `DJANGO_SECURE_HSTS_*`.
  - Conviene empezar HSTS con un valor bajo, como `3600`, y subirlo cuando todo funcione.
  - Si un proxy termina el HTTPS, activa también `DJANGO_DETRAS_DE_PROXY=True`.
- [ ] **Usuario de MySQL con permisos mínimos.** La aplicación solo necesita `SELECT, INSERT, UPDATE, DELETE` sobre `festival_votaciones.*`. Las migraciones se ejecutan con otro usuario que tenga `CREATE, ALTER, INDEX, REFERENCES, DROP`.
- [ ] `python manage.py migrate` y `python manage.py crear_grupos`.
- [ ] `python manage.py collectstatic --noinput`: copia los estáticos a `staticfiles/` y WhiteNoise los sirve.
- [ ] **Servidor WSGI**, no `runserver`:
  - en Windows, `pip install waitress` y luego `waitress-serve --port=8000 config.wsgi:application`;
  - en Linux, `pip install gunicorn` y luego `gunicorn config.wsgi`.
- [ ] **Respaldos programados:** `python manage.py respaldar_base` con el Programador de tareas de Windows o con `cron`.
- [ ] `python manage.py check --deploy` sin advertencias.

**Registro de errores:**
- Los errores 500, los accesos denegados, los fallos de CSRF y los encabezados `Host` no permitidos se guardan en `logs/festival.log`.
- Es un archivo rotativo de 1 MB con 5 copias, y la carpeta `logs/` no se sube a Git. Los errores también salen en consola.
- No se registran correos, contraseñas ni datos de los votos.

**Páginas de error:** las de 400, 403, 404, 500 y fallo de CSRF están en español, en `templates/`. La de 500 no consulta la base de datos.

## 16. Respaldos y restauración

```bash
python manage.py respaldar_base
```

- **Qué guarda:** la base configurada en `DB_NAME`, en `respaldos/AAAA-MM-DD_HHMM.sql`. Esa carpeta no se sube a Git.
- **Herramienta:** usa `mysqldump`, que busca en el PATH y en la instalación de MySQL en Windows. Si no lo encuentra, indícale la ruta con `--mysqldump`.
- **Contraseña:** nunca va en la línea de comandos. Se pasa en un archivo de opciones temporal que se borra al terminar.

**Para restaurar,** crea antes la base vacía si no existe, como en la sección 5. Luego hay dos formas:

- **En PowerShell,** con `cmd /c`, porque PowerShell no admite `<`:
  ```powershell
  cmd /c "mysql -u festival_app -p festival_votaciones < respaldos\2026-11-16_2300.sql"
  ```
  Si `mysql` no está en el PATH, usa la ruta completa: `"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"`.
- **En MySQL Workbench:** **Server → Data Import → Import from Self-Contained File**. Elige el archivo `.sql` y la base de destino, y pulsa **Start Import**.

## 17. Integración continua

[`.github/workflows/pruebas.yml`](.github/workflows/pruebas.yml) se ejecuta en GitHub Actions en cada push y cada pull request.

**Entorno:** Ubuntu, Python 3.11 y MySQL 8.0 como servicio.

**Pasos:**
1. `pip install -r requirements.txt`;
2. `python manage.py makemigrations --check --dry-run`;
3. `python manage.py test`, con todas las pruebas, incluida CP-09 contra MySQL.

**Credenciales:** el flujo no tiene ninguna escrita.
- MySQL corre en un contenedor efímero.
- La contraseña de `festival_app` y la `SECRET_KEY` se generan al empezar cada ejecución y se ocultan en el registro.

El resultado se ve en la pestaña **Actions** del repositorio y en cada pull request.

## Estructura

```
config/       configuración, rutas, WSGI y vistas de error (vistas_error.py)
cuentas/      Usuario, registro, inicio y cierre de sesión (CU-01)
  grupos.py     perfiles y permisos del grupo «Administración del festival»
  management/commands/crear_grupos.py
festival/     Edición, Categoría, Votación y Opción; vistas públicas (CU-02, CU-04)
  admin.py      admin dinámico: acciones de estado, duplicar edición, columna de votos
  servicios.py  duplicar_edicion
  api.py        API GET /api/categorias/
  reglas.py     reglas de negocio definidas y pendientes
  management/commands/   cargar_datos_prueba, preparar_demo, respaldar_base
votos/        Voto y Registro de auditoría (CU-03, CU-05, CU-06)
  servicios.py  registrar_voto y sus validaciones
  resultados.py conteos de resultados y visibilidad pública
  views.py      votar, confirmar, comprobante, «Mis votos» y resultados
  concurrencia.py, management/commands/probar_concurrencia.py   demostración de CP-09
templates/    plantillas (base.html, páginas de error, festival/, votos/, registration/ y admin/)
static/       CSS y JavaScript del sitio
.github/      integración continua
prototipo/    prototipo estático de la Entrega 1; referencia visual, no se sirve
```

## Equipo y forma de trabajo

Cada parte se trabaja en su propia rama y con sus propios commits.

| Integrante | Entrega 2 | Entrega 3 | Entrega final |
|---|---|---|---|
| 1 | Base del proyecto, configuración, MySQL, modelo Usuario y README | Modelo Voto, migración, restricción de unicidad y servicio `registrar_voto` | Administración dinámica: una edición activa, acciones de votación, duplicar edición y prueba «2028» |
| 2 | Modelos de festival y votos, migraciones, admin y datos de prueba | Vistas, formulario, confirmación y plantillas de votación | Perfiles y permisos, menú, páginas de error y seguridad para despliegue |
| 3 | Registro, inicio y cierre de sesión | «Mis votos», admin de votos y API GET | Resultados para el personal y resultados públicos según su visibilidad |
| 4 | Vistas públicas, plantillas, estilos y pruebas | Pruebas CP-01 a CP-10 (incluida la de concurrencia), README y evidencias | Base de demostración, concurrencia en base temporal, respaldos, integración continua y README |
