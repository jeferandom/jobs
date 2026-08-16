"""Entry point del sistema de scraping de empleos.

Modos de uso:
  python src/main.py                    → CLI interactivo
  python src/main.py --cli --keyword X --source Y
  python src/main.py --web              → UI web en navegador
"""

import argparse
import csv
import logging
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scrapers.computrabajo import ComputrabajoScraper
from src.scrapers.base import JobSource
from src.models.job import Job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def get_scrapers() -> list[JobSource]:
    """Retorna la lista de adaptadores disponibles."""
    return [
        ComputrabajoScraper(),
    ]


def run_scraper(keyword: str, source_name: str | None = None, limit: int = 100) -> list[Job]:
    """Ejecuta el scraper para la palabra clave y fuente indicadas."""
    scrapers = get_scrapers()

    if source_name:
        scrapers = [s for s in scrapers if s.name == source_name]
        if not scrapers:
            logger.error(f"Fuente no encontrada: {source_name}")
            return []

    all_jobs: list[Job] = []
    for scraper in scrapers:
        logger.info(f"Scrapeando {scraper.name}...")
        jobs = scraper.search(keyword, limit=limit)
        all_jobs.extend(jobs)

    return all_jobs[:limit]


def save_to_csv(jobs: list[Job], filename: str = "jobs.csv") -> str:
    """Guarda una lista de Job en un archivo CSV. Retorna la ruta del archivo."""
    if not jobs:
        logger.warning("No hay ofertas para guardar")
        return ""

    Path("data").mkdir(exist_ok=True)
    fieldnames = list(jobs[0].__dataclass_fields__.keys())
    filepath = Path("data") / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            writer.writerow(job.__dict__)

    logger.info(f"Guardadas {len(jobs)} ofertas en {filepath}")
    return str(filepath)


# =====================
# CLI
# =====================

def run_cli() -> None:
    """Modo CLI con argparse."""
    parser = argparse.ArgumentParser(description="Jobs Scraper CLI")
    parser.add_argument("--keyword", "-k", default=None, help="Palabra clave de búsqueda")
    parser.add_argument("--source", "-s", default=None, help="Fuente de empleo (ej: computrabajo)")
    parser.add_argument("--output", "-o", default=None, help="Nombre del archivo CSV de salida")
    parser.add_argument("--limit", "-l", type=int, default=100, help="Número máximo de ofertas a obtener (default: 100)")
    parser.add_argument("--list-sources", action="store_true", help="Listar fuentes disponibles")
    parser.add_argument("--web", action="store_true", help="Iniciar UI web en el navegador")

    args = parser.parse_args()

    if args.list_sources:
        print("Fuentes disponibles:")
        for s in get_scrapers():
            print(f"  - {s.name}")
        return

    keyword = args.keyword or input("Palabra clave de búsqueda: ").strip() or "desarrollador"
    filename = args.output or f"jobs_{keyword.replace(' ', '_')}.csv"

    jobs = run_scraper(keyword, args.source, limit=args.limit)
    save_to_csv(jobs, filename)


# =====================
# Web UI
# =====================

HTML_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jobs Scraper</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .card { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 100%; max-width: 480px; }
        h1 { font-size: 1.5rem; margin-bottom: 1.5rem; color: #1a1a2e; }
        label { display: block; margin-bottom: 0.25rem; font-weight: 600; color: #333; font-size: 0.9rem; }
        input, select { width: 100%; padding: 0.6rem; margin-bottom: 1rem; border: 1px solid #ddd; border-radius: 6px; font-size: 1rem; }
        button { width: 100%; padding: 0.75rem; background: #4361ee; color: white; border: none; border-radius: 6px; font-size: 1rem; cursor: pointer; }
        button:hover { background: #3a56d4; }
        button:disabled { background: #aaa; cursor: not-allowed; }
        #result { margin-top: 1.5rem; padding: 1rem; border-radius: 6px; display: none; }
        #result.success { background: #d4edda; color: #155724; }
        #result.error { background: #f8d7da; color: #721c24; }
        .spinner { display: none; text-align: center; margin-top: 1rem; }
        .spinner.active { display: block; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Jobs Scraper</h1>
        <form id="form">
            <label for="keyword">Palabra clave</label>
            <input type="text" id="keyword" placeholder="desarrollador" value="desarrollador" required>

            <label for="limit">Número de resultados</label>
            <input type="number" id="limit" min="1" max="5000" value="100" placeholder="100">

            <label for="source">Fuente de empleo</label>
            <select id="source">
                <option value="">Todas las fuentes</option>
                __SOURCES__
            </select>

            <button type="submit" id="btn">Buscar empleos</button>
        </form>
        <div class="spinner" id="spinner">Buscando... esto puede tardar unos minutos</div>
        <div id="result"></div>
    </div>

    <script>
        document.getElementById('form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btn');
            const spinner = document.getElementById('spinner');
            const result = document.getElementById('result');

            btn.disabled = true;
            spinner.classList.add('active');
            result.style.display = 'none';

            const keyword = document.getElementById('keyword').value;
            const source = document.getElementById('source').value;
            const limit = document.getElementById('limit').value;

            try {
                const resp = await fetch(`/search?keyword=${encodeURIComponent(keyword)}&source=${encodeURIComponent(source)}&limit=${limit}`);
                const data = await resp.json();
                result.className = 'success';
                result.textContent = `${data.count} ofertas guardadas en ${data.file}`;
            } catch (err) {
                result.className = 'error';
                result.textContent = 'Error: ' + err.message;
            }

            result.style.display = 'block';
            spinner.classList.remove('active');
            btn.disabled = false;
        });
    </script>
</body>
</html>
"""


class WebHandler(BaseHTTPRequestHandler):
    """Handler para la UI web."""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            sources_options = "".join(
                f'<option value="{s.name}">{s.name.capitalize()}</option>'
                for s in get_scrapers()
            )
            page = HTML_PAGE.replace("__SOURCES__", sources_options)
            self._respond(200, page, "text/html; charset=utf-8")

        elif parsed.path == "/search":
            params = parse_qs(parsed.query)
            keyword = params.get("keyword", ["desarrollador"])[0]
            source = params.get("source", [""])[0] or None
            limit = int(params.get("limit", ["100"])[0])

            jobs = run_scraper(keyword, source, limit=limit)
            filename = f"jobs_{keyword.replace(' ', '_')}.csv"
            filepath = save_to_csv(jobs, filename)

            import json

            response = json.dumps({"count": len(jobs), "file": filepath})
            self._respond(200, response, "application/json")

        else:
            self._respond(404, "Not found", "text/plain")

    def _respond(self, code: int, body: str, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        logger.info(f"HTTP {format % args}")


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


def run_web(port: int = 8000) -> None:
    """Inicia el servidor web."""
    server = ReusableHTTPServer(("localhost", port), WebHandler)
    url = f"http://localhost:{port}"
    logger.info(f"Servidor web en {url}")
    webbrowser.open(url)
    server.serve_forever()


# =====================
# Entry point
# =====================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jobs Scraper")
    parser.add_argument("--web", action="store_true", help="Iniciar UI web en el navegador")
    args, remaining = parser.parse_known_args()

    if args.web:
        run_web()
    else:
        run_cli()
