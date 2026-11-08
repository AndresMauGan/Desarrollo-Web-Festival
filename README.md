# Sistema de votaciones · Festival de la Leyenda Vallenata 2027

Proyecto universitario de Desarrollo Web (Fundación Universitaria del Área Andina).

Aplicación web en **Django 5.2 (patrón MVT) + MySQL 8** para el voto del público en el Festival. Las personas se registran, eligen una categoría, seleccionan una opción, confirman y el voto queda guardado en MySQL. Cada persona puede votar **una sola vez por categoría y edición**, aunque la categoría tenga varias votaciones (subeventos) abiertas.

Qué incluye:
- **Consulta pública:** ediciones, categorías, votaciones y opciones desde MySQL.
- **Votación con sesión iniciada:** elegir, confirmar y recibir un comprobante.
- **Validaciones en el servidor:** categorías cerradas o no habilitadas, opciones que no corresponden, solicitudes sin sesión y votos duplicados, incluidas las solicitudes simultáneas.
- **«Mis votos»:** cada persona ve las categorías en las que votó.
- **Administración:** el personal consulta los votos en Django Admin, en modo de solo lectura.
- **API de consulta:** `GET /api/categorias/` devuelve en JSON las categorías y sus opciones.

## Tecnologías

| Tecnología | Versión |
|---|---|
| Python | 3.11 o superior (probado con 3.11.2) |
| Django | 5.2.18 (LTS) |
| MySQL Server | 8.0.11 o superior (probado con 8.0.33), utf8mb4 |
| mysqlclient | 2.3.0 |
| Pillow | 12.3.0 (fotos opcionales de las opciones) |
| python-dotenv | 1.2.4 (lee el archivo `.env`) |

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

Instala las dependencias:

```bash
pip install -r requirements.txt
```

En Windows, `mysqlclient` se instala sin compilar. En Linux hace falta antes `sudo apt install pkg-config libmysqlclient-dev`, y en macOS `brew install mysql-client pkg-config`.

## 2. Crear la base de datos y el usuario de MySQL

1. Inicia el servidor de MySQL. En Windows: aplicación **Servicios** → `MySQL80` → Iniciar, o `net start MySQL80` en una terminal de administrador.
2. Abre MySQL Workbench (o el cliente `mysql`) con tu cuenta `root` y ejecuta lo siguiente. Cambia `<contraseña>` por una clave tuya; no la escribas en ningún archivo del repositorio.

```sql
CREATE DATABASE festival_votaciones CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'festival_app'@'localhost' IDENTIFIED BY '<contraseña>';
GRANT ALL PRIVILEGES ON festival_votaciones.* TO 'festival_app'@'localhost';
-- Permiso para la base temporal que crea «python manage.py test»
GRANT ALL PRIVILEGES ON test_festival_votaciones.* TO 'festival_app'@'localhost';
FLUSH PRIVILEGES;
```

## 3. Configurar las variables de entorno

Copia la plantilla y complétala. El archivo `.env` queda fuera de Git: **nunca subas contraseñas ni claves al repositorio**.

```bash
cp .env.example .env
```

| Variable | Valor |
|---|---|
| `DJANGO_SECRET_KEY` | Genérala con `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DJANGO_DEBUG` | `True` solo en desarrollo |
| `DB_NAME`, `DB_USER` | `festival_votaciones` y `festival_app`, como en el paso 2 |
| `DB_PASSWORD` | La contraseña que pusiste en el paso 2 |
| `DB_HOST`, `DB_PORT` | `localhost` y `3306` |

Si falta una variable, Django se detiene con un mensaje que dice cuál.

## 4. Migraciones, administrador y datos de prueba

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py cargar_datos_prueba
```

- `migrate` crea las tablas. Las migraciones de esta entrega son:
  - [`festival/migrations/0002_quita_limite_votos_por_usuario.py`](festival/migrations/0002_quita_limite_votos_por_usuario.py): quita el límite por votación, que ya no aplica.
  - [`votos/migrations/0002_voto_categoria_edicion_unicidad.py`](votos/migrations/0002_voto_categoria_edicion_unicidad.py): agrega categoría y edición al voto y crea la restricción única.
- `createsuperuser` pide correo, nombre para mostrar y contraseña. Las cuentas se identifican con el correo.
- `cargar_datos_prueba` carga las ediciones 2026 y 2027, sus categorías, votaciones en todos los estados y opciones con nombres ficticios.
  - **No crea usuarios:** los votantes se registran desde la interfaz y el personal con `createsuperuser`.
  - **Horario:** las votaciones abiertas quedan dentro de su horario desde una hora antes de la carga hasta 30 días después, así se puede votar hoy (RN-03).
  - **Categorías para votar hoy:** Acordeonera Mayor, con dos subeventos abiertos, y Piquería Mayor.
  - Se puede ejecutar varias veces sin duplicar nada. Vuelve a ejecutarlo si pasan los 30 días.

## 5. Ejecutar el proyecto

```bash
python manage.py runserver
```

| Página | Dirección |
|---|---|
| Sitio público | http://127.0.0.1:8000/ |
| Categorías de la edición activa | http://127.0.0.1:8000/categorias/ |
| Registro e inicio de sesión | http://127.0.0.1:8000/cuentas/registro/ · http://127.0.0.1:8000/cuentas/ingresar/ |
| Mis votos | http://127.0.0.1:8000/votar/mis-votos/ |
| API | http://127.0.0.1:8000/api/categorias/ |
| Administración | http://127.0.0.1:8000/admin/ |

## 6. Cómo votar

1. **Crea una cuenta** en *Registrarse* (`/cuentas/registro/`) o inicia sesión. Sin sesión, al intentar votar el sitio te lleva al inicio de sesión y después te devuelve a la categoría.
2. **Elige una categoría** con una votación *En vivo* y pulsa **Votar en esta categoría** (`/votar/categoria/<id>/`).
3. **Selecciona una opción.** Si la categoría tiene varios subeventos abiertos, se muestran todos, pero solo puedes elegir una opción entre ellos. Pulsa **Continuar**.
4. **Confirma.** La pantalla de confirmación advierte que el voto es irreversible. Pulsa **Confirmar voto**.
5. **Recibe el comprobante,** con un código como `VV-1A2B-3C4D`, la fecha y la hora. Lo puedes volver a ver en **Mis votos**.

Si vuelves a la categoría después de votar, verás tu voto y el comprobante en lugar del formulario. Puedes votar en las demás categorías abiertas.

El personal consulta los votos en **Administración → Votos**. Allí puede filtrar por edición, categoría y fecha, y buscar por correo. Esa sección es de solo lectura, porque los votos no se modifican ni se borran (RN-02).

## 7. API de consulta: `GET /api/categorias/`

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

## 8. Dónde se controla la unicidad (un voto por usuario, categoría y edición)

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

## 9. Pruebas

```bash
python manage.py test                          # todas las pruebas (79)
python manage.py test votos.test_casos_prueba  # solo los casos CP-01 a CP-10
```

Django crea y borra la base `test_festival_votaciones`; por eso el usuario de MySQL necesita el permiso del paso 2. Los casos de la guía están en [`votos/test_casos_prueba.py`](votos/test_casos_prueba.py):

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
python manage.py probar_concurrencia --categoria <id>
```

- **Qué hace:** envía varias solicitudes de voto a la vez a la misma categoría, cada una en su propio hilo y con su propia conexión a MySQL.
- **Qué muestra:** cuántas se registraron, cuántas rechazó Django y cuántas detuvo la restricción de MySQL. Al final cuenta los votos con SQL directo; siempre debe quedar uno.
- **`--forzar-carrera`:** todas las solicitudes pasan las validaciones de Django antes de que alguna inserte, así que solo MySQL puede detener los duplicados.
- **Datos que deja:** cada ejecución crea un votante desechable con correo `concurrencia-…@example.invalid` y sin contraseña, así que nadie puede iniciar sesión con él.
  - Ese votante y su voto quedan en la base, porque los votos son inmutables (RN-02).
  - Úsalo solo en la base de desarrollo.

## Estructura

```
config/       configuración, rutas principales y WSGI
cuentas/      modelo Usuario, registro, inicio y cierre de sesión (CU-01)
festival/     Edición, Categoría, Votación y Opción; vistas públicas (CU-02, CU-04)
  api.py        API GET /api/categorias/
  reglas.py     reglas de negocio definidas y pendientes
votos/        Voto y Registro de auditoría (CU-03, CU-06)
  servicios.py  registrar_voto y sus validaciones
  views.py      votar, confirmar, comprobante y «Mis votos»
  concurrencia.py, management/commands/probar_concurrencia.py   demostración de CP-09
  test_casos_prueba.py   casos CP-01 a CP-10
templates/    plantillas (base.html, festival/, votos/ y registration/)
static/       CSS y JavaScript del sitio
prototipo/    prototipo estático de la Entrega 1; referencia visual, no se sirve
```

## Equipo y forma de trabajo

Cada parte se trabaja en su propia rama y con sus propios commits.

| Integrante | Entrega 2 | Entrega 3 |
|---|---|---|
| 1 | Base del proyecto, configuración, MySQL, modelo Usuario y README | Modelo Voto, migración, restricción de unicidad y servicio `registrar_voto` |
| 2 | Modelos de festival y votos, migraciones, admin y datos de prueba | Vistas, formulario, confirmación y plantillas de votación |
| 3 | Registro, inicio y cierre de sesión | «Mis votos», admin de votos y API GET |
| 4 | Vistas públicas, plantillas, estilos y pruebas | Pruebas CP-01 a CP-10 (incluida la de concurrencia), README y evidencias |
