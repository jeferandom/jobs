# Jobs Scraper

Proyecto de scraping de páginas web de empleos con soporte de autenticación.

## Uso

### CLI

```bash
# Interactivo (pide keyword por teclado)
python3 src/main.py

# Con argumentos
python3 src/main.py --keyword desarrollador --source computrabajo --output jobs.csv

# Listar fuentes disponibles
python3 src/main.py --list-sources
```

### UI Web

```bash
python3 src/main.py --web
```

Abre el navegador en `http://localhost:8000` con:
- **Panel de autenticación** para iniciar sesión en CompuTrabajo
- **Formulario de búsqueda** por palabra clave
- **Botón "Mis postulaciones"** para ver ofertas aplicadas

## Autenticación

### Login con credenciales (recomendado)

1. Click "Iniciar sesión" en el panel de auth
2. Seleccionar pestaña "Email y contraseña"
3. Ingresar email y contraseña de CompuTrabajo
4. Esperar a que cambie a "Conectado ✓"
5. La sesión se guarda en `data/sessions/computrabajo.json`

### Login con Google

1. Click "Iniciar sesión" → pestaña "Google"
2. Se abre una ventana del navegador
3. Hacer login con Google manualmente
4. La ventana se cierra y el estado cambia a "Conectado ✓"

### Ver postulaciones

Click "Mis postulaciones" para scrapear las ofertas a las que estás aplicado en CompuTrabajo.

## Diagrama de la Aplicación

```
┌─────────────────────────────────────────────────────────────────┐
│                          main.py                                │
│   ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│   │   CLI       │    │   Web UI     │    │  Auth Providers  │   │
│   │  argparse   │    │ http.server  │    │  ┌────────────┐  │   │
│   └──────┬──────┘    └──────┬───────┘    │  │ Credentials│  │   │
│          └──────────┬───────┘            │  │ GoogleOAuth│  │   │
│                     ▼                    │  └─────┬──────┘  │   │
│              run_scraper()               └────────┼─────────┘   │
│                     │                            │              │
│                     ▼                            ▼              │
│              save_to_csv()              SessionManager          │
└─────────────────────────────┬───────────────────┬───────────────┘
                              │                   │
                              ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    src/scrapers/base.py                          │
│                   class JobSource(ABC)                           │
│           ┌─────────────────────────────────┐                   │
│           │  name: str                      │                   │
│           │  requires_auth: bool            │                   │
│           │  search(keyword) -> list[Job]   │                   │
│           │  get_applied_jobs() -> list[Job]│                   │
│           └─────────────────────────────────┘                   │
└─────────────────────────────┬───────────────────────────────────┘
                              │ implementa
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │Computra- │   │ Infojobs │   │ LinkedIn │
        │ .jobo    │   │ (futuro) │   │ (futuro) │
        │ (público│   └──────────┘   └──────────┘
        │  + auth) │
        └────┬─────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                src/scrapers/computrabajo.py                      │
│  fetch_page() ──► parse_job_listings() ──► list[Job]            │
│  requests + headers    BeautifulSoup + lxml                    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              src/scrapers/computrabajo_auth.py                   │
│  Playwright + storage_state ──► candidate/match ──► list[Job]   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │     data/       │
                     │  .csv / .json   │
                     │  sessions/      │
                     └─────────────────┘
```

## Estructura

```
job_scrapper/
├── src/
│   ├── __init__.py
│   ├── main.py                     # Entry point - CLI + Web UI + endpoints auth
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── base.py                 # AuthProvider (ABC) + LoginStatus
│   │   ├── session_manager.py      # Gestión de sesiones (storage_state)
│   │   ├── google_oauth.py         # Login manual con Google (ventana visible)
│   │   └── credentials.py          # Login automatizado email/password (headless)
│   ├── models/
│   │   ├── __init__.py
│   │   └── job.py                  # @dataclass Job
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py                 # ABC JobSource + SessionExpiredError
│   │   ├── computrabajo.py         # Scraping público (requests + BS4)
│   │   └── computrabajo_auth.py    # Scraping autenticado (Playwright)
│   └── analysis/
│       ├── __init__.py
│       ├── wordcloud_gen.py
│       ├── word_frequency.py
│       └── stop_words.py
├── data/
│   ├── jobs_*.json                 # Resultados de scraping
│   └── sessions/                   # Sesiones autenticadas (gitignored)
│       └── computrabajo.json
├── scraper/                        # Scraper legacy (prototipo anterior)
├── ARCHITECTURE.md                 # Documentación de arquitectura
├── requirements.txt
└── README.md
```

## Instalación

```bash
pip install -r requirements.txt
playwright install chromium
```

## Modelo `Job` (`src/models/job.py`)

```python
@dataclass
class Job:
    title: str
    company: str
    location: str
    source: str
    scraped_at: str
    salary: str | None
    job_type: str | None   # presencial, remoto, hibrido
    url: str | None
    is_urgent: bool
    is_featured: bool
```

## Interfaz `JobSource` (`src/scrapers/base.py`)

```python
class JobSource(ABC):
    name: str
    requires_auth: bool = False

    def search(keyword, limit) -> list[Job]          # búsqueda pública
    def get_applied_jobs(self) -> list[Job]: ...     # postulaciones (auth)
```

## Adaptadores

| Fuente | Archivo | Tipo | Estado |
|---|---|---|---|
| Computrabajo (público) | `src/scrapers/computrabajo.py` | requests + BS4 | Implementado |
| Computrabajo (auth) | `src/scrapers/computrabajo_auth.py` | Playwright | Implementado |
| Infojobs | `src/scrapers/infojobs.py` | - | Pendiente |
| LinkedIn | `src/scrapers/linkedin.py` | - | Pendiente |

## Agregar una nueva fuente

1. Crear `src/scrapers/{fuente}.py`
2. Implementar `JobSource` con `name` y `search()`
3. Si requiere auth, crear proveedor en `src/auth/`
4. Registrar en `get_scrapers()` y `_auth_providers` de `main.py`

## Endpoints API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/auth/status` | Estado de autenticación por proveedor |
| POST | `/api/auth/start/{provider}` | Login manual (ventana Playwright) |
| POST | `/api/auth/login/{provider}` | Login con credenciales `{email, password}` |
| POST | `/api/auth/cancel/{provider}` | Cancelar login en progreso |
| POST | `/api/auth/logout/{provider}` | Eliminar sesión guardada |
| GET | `/api/auth/check/{provider}` | Verificar estado del login |
| GET | `/api/applied/{provider}` | Obtener postulaciones (requiere sesión) |

## Dependencias

- `requests` - Peticiones HTTP
- `beautifulsoup4` - Parsing HTML
- `playwright` - Navegación web autenticada
- `selenium` - Navegación web dinámica
- `pandas` - Manipulación y exportación de datos
- `lxml` - Parser XML/HTML alternativo
- `wordcloud` - Generación de nubes de palabras
- `matplotlib` - Gráficos

## Estado del Proyecto

| Componente | Estado |
|---|---|
| Scraping público (search) | ✅ Implementado |
| Login con credenciales | ✅ Implementado |
| Login con Google OAuth | ⚠️ Bloqueado por Google |
| Scraping autenticado (postulaciones) | ✅ Implementado |
| UI Web con modal auth | ✅ Implementado |
