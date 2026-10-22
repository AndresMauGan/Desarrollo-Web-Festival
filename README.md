# Sistema de votaciones · Festival de la Leyenda Vallenata 2027

Proyecto universitario de Desarrollo Web (Fundación Universitaria del Área Andina).
Primera versión funcional con **Python + Django 5.2 (patrón MVT) + MySQL 8**.

## Requisitos

- Python 3.11 o superior
- MySQL Server 8.0.11 o superior (en Windows sirve MySQL Installer, que incluye MySQL Workbench)
- Git

## 1. Clonar e instalar dependencias

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
2. Abre MySQL Workbench (o el cliente `mysql`) con tu cuenta `root` y ejecuta lo siguiente, cambiando `<contraseña>` por una clave tuya:

```sql
CREATE DATABASE festival_votaciones CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'festival_app'@'localhost' IDENTIFIED BY '<contraseña>';
GRANT ALL PRIVILEGES ON festival_votaciones.* TO 'festival_app'@'localhost';
-- Permiso para la base temporal que crea «python manage.py test»
GRANT ALL PRIVILEGES ON test_festival_votaciones.* TO 'festival_app'@'localhost';
FLUSH PRIVILEGES;
```

## 3. Configurar las variables de entorno

Copia la plantilla y complétala. El archivo `.env` queda fuera de Git; **nunca subas contraseñas ni claves al repositorio**.

```bash
cp .env.example .env
```

- `DJANGO_SECRET_KEY`: genera una con
  `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- `DB_PASSWORD`: la contraseña que pusiste en el paso 2.

Si falta una variable, Django se detiene con un mensaje que dice cuál.

## 4. Crear las tablas, el administrador y los datos de prueba

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py cargar_datos_prueba
```

- `createsuperuser` pide correo, nombre para mostrar y contraseña: las cuentas se identifican con el correo.
- `cargar_datos_prueba` carga las ediciones 2026 y 2027, las cuatro categorías, votaciones en distintos estados y opciones con nombres ficticios.

## 5. Ejecutar

```bash
python manage.py runserver
```

- Sitio público: http://127.0.0.1:8000/
- Administración: http://127.0.0.1:8000/admin/

## 6. Pruebas

```bash
python manage.py test
```

Django crea y borra la base `test_festival_votaciones`; por eso el usuario de MySQL necesita el permiso del paso 2.

## Estructura

```
config/       configuración, rutas principales y WSGI
cuentas/      modelo Usuario, registro, inicio y cierre de sesión (CU-01)
festival/     Edición, Categoría, Votación y Opción; vistas públicas (CU-02, CU-04)
votos/        Voto y Registro de auditoría: solo estructura en esta entrega
templates/    plantillas compartidas (base.html y registration/)
static/       CSS y JavaScript del sitio
prototipo/    prototipo estático de la Entrega 1; referencia visual, no se sirve
```

## Equipo y forma de trabajo

Cada integrante trabaja en su propia rama y hace sus propios commits.

| Integrante | Parte |
|---|---|
| 1 | Base del proyecto, configuración, MySQL, modelo Usuario y README |
| 2 | Modelos de festival y votos, migraciones, admin y datos de prueba |
| 3 | Registro, inicio y cierre de sesión |
| 4 | Vistas públicas, plantillas, estilos y pruebas |
