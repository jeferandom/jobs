# Jobs Scraper

Proyecto de scraping de páginas web de empleos.
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

Abre el navegador en `http://localhost:8000` con un formulario para seleccionar fuente e ingresar palabra clave.

## Diagrama de la Aplicación

```
┌─────────────────────────────────────────────────────────────────┐
│                          main.py                                │
│          ┌─────────────┐          ┌──────────────┐              │
│          │   CLI       │          │   Web UI     │              │
│          │  argparse   │          │ http.server  │              │
│          └──────┬──────┘          └──────┬───────┘              │
│                 └────────────┬───────────┘                      │
│                              ▼                                  │
│                       run_scraper()                             │
│                              │                                  │
│                              ▼                                  │
│                       save_to_csv()                             │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    src/scrapers/base.py                          │
│                   class JobSource(ABC)                           │
│           ┌─────────────────────────────────┐                   │
│           │  name: str                      │                   │
│           │  search(keyword) -> list[Job]   │                   │
│           └─────────────────────────────────┘                   │
└─────────────────────────────┬───────────────────────────────────┘
                              │ implementa
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │Computra- │   │ Infojobs │   │ LinkedIn │
        │ .jobo    │   │ (futuro) │   │ (futuro) │
        └────┬─────┘   └──────────┘   └──────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                src/scrapers/computrabajo.py                      │
│                                                                 │
│  fetch_page() ──► parse_job_listings() ──► list[Job]            │
│       │                    │                                    │
│       ▼                    ▼                                    │
│  requests + headers    BeautifulSoup + lxml                    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   co.computra-   │
                    │    jobajo.com    │
                    │  (paginas 1-N)  │
                    └────────┬─────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     src/models/job.py                            │
│                   @dataclass Job                                 │
│  title | company | location | source | salary | url | ...       │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │     data/       │
                     │  .csv / .json   │
                     └─────────────────┘
```

## Estructura

```
jobs/
├── src/
│   ├── __init__.py
│   ├── main.py                     # Entry point - usa adaptadores
│   ├── models/
│   │   ├── __init__.py
│   │   └── job.py                  # @dataclass Job
│   └── scrapers/
│       ├── __init__.py
│       ├── base.py                 # ABC JobSource (interfaz)
│       └── computrabajo.py         # Adaptador Computrabajo
├── scraper/                        # Scraper legacy (prototipo anterior)
│   ├── config.py
│   ├── http_client.py
│   ├── parser.py
│   ├── scraper.py
│   ├── storage.py
│   └── main.py
├── data/                           # Output de datos scrapeados
├── requirements.txt
└── README.md
```

## Instalación

```bash
pip install -r requirements.txt
```


## Arquitectura

### Modelo `Job` (`src/models/job.py`)

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

### Interfaz `JobSource` (`src/scrapers/base.py`)

```python
class JobSource(ABC):
    @property
    def name(self) -> str: ...

    def search(self, keyword: str) -> list[Job]: ...
```

### Adaptadores

| Fuente | Archivo | Estado |
|---|---|---|
| Computrabajo | `src/scrapers/computrabajo.py` | Implementado |
| Infojobs | `src/scrapers/infojobs.py` | Pendiente |
| LinkedIn | `src/scrapers/linkedin.py` | Pendiente |

### Agregar una nueva fuente

1. Crear `src/scrapers/{fuente}.py`
2. Implementar `JobSource` con `name` y `search()`
3. Agregar en `get_scrapers()` de `main.py`

## Requerimientos

### Funcionales

- Dada una palabra clave y una fuente (Infojobs, Computrabajo, LinkedIn), consultar empleos disponibles
- Utilizar scraping o API cuando la fuente lo permita
- Devolver resultados en formato JSON con campos: título, empresa, ubicación, fecha de extracción y fuente
- Soporte para scraping estático (requests + BeautifulSoup) y dinámico (Selenium)
- Guardar resultados en formato CSV

### No Funcionales

- Manejo de errores en peticiones HTTP
- User-Agent configurable para evitar bloqueos
- Codificación UTF-8 en archivos de salida
- Código modular y extensible

### Dependencias

- `requests` - Peticiones HTTP
- `beautifulsoup4` - Parsing HTML
- `selenium` - Navegación web dinámica
- `pandas` - Manipulación y exportación de datos
- `lxml` - Parser XML/HTML alternativo
