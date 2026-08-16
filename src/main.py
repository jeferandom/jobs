"""Entry point del sistema de scraping de empleos.

Modos de uso:
  python src/main.py                    → CLI interactivo
  python src/main.py --cli --keyword X --source Y
  python src/main.py --web              → UI web en navegador
"""

import argparse
import csv
import json
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


def save_to_json(jobs: list[Job], filename: str = "jobs.json") -> str:
    """Guarda una lista de Job en un archivo JSON. Retorna la ruta del archivo."""
    if not jobs:
        logger.warning("No hay ofertas para guardar en JSON")
        return ""

    Path("data").mkdir(exist_ok=True)
    filepath = Path("data") / filename

    data = [job.__dict__ for job in jobs]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Guardadas {len(jobs)} ofertas en JSON: {filepath}")
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
    save_to_json(jobs, f"jobs_{keyword.replace(' ', '_')}.json")
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
        body { font-family: system-ui, sans-serif; background: #f0f2f5; min-height: 100vh; padding: 2rem; }
        .layout { max-width: 1100px; margin: 0 auto; display: flex; gap: 1.5rem; align-items: flex-start; }
        .card { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); flex: 0 0 420px; }
        .panel { background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); flex: 1; min-width: 0; }
        h1 { font-size: 1.5rem; margin-bottom: 1.5rem; color: #1a1a2e; }
        .panel h2 { font-size: 1.1rem; margin-bottom: 1rem; color: #1a1a2e; }
        label { display: block; margin-bottom: 0.25rem; font-weight: 600; color: #333; font-size: 0.9rem; }
        input, select { width: 100%; padding: 0.6rem; margin-bottom: 1rem; border: 1px solid #ddd; border-radius: 6px; font-size: 1rem; }
        .checkbox-row { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; }
        .checkbox-row input[type="checkbox"] { width: auto; margin-bottom: 0; }
        .checkbox-row label { margin-bottom: 0; font-weight: 400; }
        button { width: 100%; padding: 0.75rem; background: #4361ee; color: white; border: none; border-radius: 6px; font-size: 1rem; cursor: pointer; }
        button:hover { background: #3a56d4; }
        button:disabled { background: #aaa; cursor: not-allowed; }
        button.secondary { background: #2ecc71; margin-top: 0.75rem; }
        button.secondary:hover { background: #27ae60; }
        #result { margin-top: 1.5rem; padding: 1rem; border-radius: 6px; display: none; }
        #result.success { background: #d4edda; color: #155724; }
        #result.error { background: #f8d7da; color: #721c24; }
        .spinner { display: none; text-align: center; margin-top: 1rem; }
        .spinner.active { display: block; }
        .file-list { list-style: none; display: flex; flex-direction: column; gap: 0.75rem; }
        .file-item { background: #fafafa; border: 1px solid #e3e3e3; border-radius: 10px; padding: 1rem 1.25rem; transition: all 0.15s; cursor: pointer; }
        .file-item:hover { background: #f0f0f0; border-color: #ccc; transform: translateY(-1px); }
        .file-header { display: flex; align-items: start; justify-content: space-between; gap: 1rem; }
        .file-info { flex: 1; min-width: 0; }
        .file-name { font-weight: 700; color: #1a1a2e; font-size: 1rem; word-break: break-all; }
        .file-keyword { font-weight: 700; color: #1a1a2e; font-size: 1rem; }
        .file-count { display: inline-block; background: #4361ee; color: white; border-radius: 10px; padding: 0.1rem 0.5rem; font-size: 0.7rem; font-weight: 600; margin-left: 0.5rem; }
        .file-meta { display: flex; gap: 1rem; color: #888; font-size: 0.8rem; margin-top: 0.4rem; }
        .file-meta span { display: inline-flex; align-items: center; gap: 0.2rem; }
        .file-item .view-btn { flex-shrink: 0; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; padding: 0; background: #4361ee; color: white; border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; }
        .file-item .view-btn:hover { background: #3a56d4; }
        .empty-msg { text-align: center; color: #888; padding: 2rem 0; font-size: 0.9rem; }
        @media (max-width: 800px) {
            .layout { flex-direction: column; }
            .card { flex: none; width: 100%; }
            .panel { flex: none; width: 100%; }
        }
    </style>
</head>
<body>
    <div class="layout">
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

                <div class="checkbox-row">
                    <input type="checkbox" id="save_csv">
                    <label for="save_csv">Guardar también en CSV</label>
                </div>

                <button type="submit" id="btn">Buscar empleos</button>
            </form>
            <div class="spinner" id="spinner">Buscando... esto puede tardar unos minutos</div>
            <div id="result"></div>
            <button class="secondary" id="btnResults" style="display:none" onclick="window.location.href='/results'">Ver resultados</button>
        </div>

        <div class="panel">
            <h2>Archivos generados</h2>
            <ul class="file-list" id="fileList"></ul>
            <div class="empty-msg" id="emptyMsg">No hay archivos generados aun.</div>
        </div>
    </div>

    <script>
        async function loadFiles() {
            const list = document.getElementById('fileList');
            const emptyMsg = document.getElementById('emptyMsg');
            try {
                const resp = await fetch('/api/files');
                const files = await resp.json();
                if (!files.length) { emptyMsg.style.display = 'block'; return; }
                emptyMsg.style.display = 'none';
                list.innerHTML = '';
                files.forEach(f => {
                    const li = document.createElement('li');
                    li.className = 'file-item';
                    const date = new Date(f.modified * 1000);
                    const dateStr = date.toLocaleDateString('es-CO');
                    const timeStr = date.toLocaleTimeString('es-CO', {hour:'2-digit', minute:'2-digit'});
                    const sizeKB = (f.size / 1024).toFixed(1);
                    const keyword = f.name.replace(/^jobs_/, '').replace(/\\.json$/, '').replace(/_/g, ' ');
                    li.innerHTML = `
                         <div class="file-header">
                             <div class="file-info">
                                 <div class="file-keyword">${keyword}<span class="file-count">${f.count} empleos</span></div>
                                 <div class="file-meta">
                                     <span>&#128337; ${dateStr} ${timeStr}</span>
                                     <span>&#128190; ${sizeKB} KB</span>
                                     <span>&#128194; ${f.name}</span>
                                 </div>
                             </div>
                             <button class="view-btn" onclick="window.location.href='/results?file=${encodeURIComponent(f.name)}'">&#128269;</button>
                         </div>
                    `;
                    list.appendChild(li);
                });
            } catch (e) {
                emptyMsg.textContent = 'Error al cargar archivos.';
                emptyMsg.style.display = 'block';
            }
        }

        loadFiles();

        document.getElementById('form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btn');
            const spinner = document.getElementById('spinner');
            const result = document.getElementById('result');
            const btnResults = document.getElementById('btnResults');

            btn.disabled = true;
            spinner.classList.add('active');
            result.style.display = 'none';
            btnResults.style.display = 'none';

            const keyword = document.getElementById('keyword').value;
            const source = document.getElementById('source').value;
            const limit = document.getElementById('limit').value;
            const saveCsv = document.getElementById('save_csv').checked;

            try {
                const resp = await fetch(`/search?keyword=${encodeURIComponent(keyword)}&source=${encodeURIComponent(source)}&limit=${limit}&save_csv=${saveCsv}`);
                const data = await resp.json();
                result.className = 'success';
                result.textContent = `${data.count} ofertas guardadas en ${data.file}`;
                btnResults.style.display = 'block';
                loadFiles();
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


RESULTS_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resultados - Jobs Scraper</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; background: #f0f2f5; padding: 2rem; }
        .header { max-width: 1000px; margin: 0 auto 1.5rem; display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
        h1 { font-size: 1.5rem; color: #1a1a2e; }
        .back-btn { padding: 0.5rem 1rem; background: #4361ee; color: white; border: none; border-radius: 6px; cursor: pointer; text-decoration: none; font-size: 0.9rem; }
        .back-btn:hover { background: #3a56d4; }
        .count { color: #666; font-size: 0.9rem; }
        .file-label { color: #888; font-size: 0.85rem; font-weight: 400; }
        .jobs-container { max-width: 1000px; margin: 0 auto; display: flex; flex-direction: column; gap: 1rem; }
        .job-card { background: white; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); padding: 1.25rem 1.5rem; transition: box-shadow 0.15s, transform 0.15s; }
        .job-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); transform: translateY(-1px); }
        .job-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
        .job-title { font-size: 1.1rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0.25rem; }
        .job-company { font-size: 0.95rem; color: #4361ee; font-weight: 600; }
        .job-badges { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.5rem; }
        .badge { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.2rem 0.55rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
        .badge.urgent { background: #fff3cd; color: #856404; }
        .badge.featured { background: #d1ecf1; color: #0c5460; }
        .badge.type { background: #e9ecef; color: #495057; }
        .badge.salary { background: #d4edda; color: #155724; }
        .job-details { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem 1.5rem; margin-top: 1rem; font-size: 0.85rem; }
        .detail-item { display: flex; flex-direction: column; gap: 0.15rem; }
        .detail-label { color: #888; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.3px; }
        .detail-value { color: #333; font-weight: 500; }
        .job-location { display: flex; align-items: center; gap: 0.4rem; color: #555; margin-top: 0.25rem; font-size: 0.85rem; }
        .job-url a { color: #4361ee; text-decoration: none; font-size: 0.85rem; }
        .job-url a:hover { text-decoration: underline; }
        .empty { text-align: center; padding: 3rem; color: #888; font-size: 1rem; }
        @media (max-width: 600px) {
            .job-details { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <a href="/" class="back-btn">Volver</a>
        <h1>Resultados</h1>
        <span class="count" id="count"></span>
        <span class="file-label" id="fileLabel"></span>
    </div>
    <div class="jobs-container" id="jobsContainer">
        <div class="empty" id="empty">No hay resultados para mostrar.</div>
    </div>

    <script>
        (async () => {
            const container = document.getElementById('jobsContainer');
            const empty = document.getElementById('empty');
            const countEl = document.getElementById('count');
            const fileLabel = document.getElementById('fileLabel');
            const params = new URLSearchParams(window.location.search);
            const file = params.get('file');
            const apiUrl = file ? `/api/results?file=${encodeURIComponent(file)}` : '/api/results';
            if (file) {
                const keyword = file.replace(/^jobs_/, '').replace(/\\.json$/, '').replace(/_/g, ' ');
                fileLabel.textContent = `Archivo: ${keyword}`;
            }
            try {
                const resp = await fetch(apiUrl);
                const jobs = await resp.json();
                if (!jobs.length) { empty.style.display = 'block'; return; }
                empty.style.display = 'none';
                countEl.textContent = `${jobs.length} ofertas`;
                jobs.forEach(j => {
                    const card = document.createElement('div');
                    card.className = 'job-card';
                    const badges = [];
                    if (j.is_urgent) badges.push('<span class="badge urgent">Urgente</span>');
                    if (j.is_featured) badges.push('<span class="badge featured">Destacado</span>');
                    if (j.job_type) badges.push(`<span class="badge type">${j.job_type}</span>`);
                    if (j.salary) badges.push(`<span class="badge salary">$${j.salary}</span>`);
                    const badgesHtml = badges.length ? `<div class="job-badges">${badges.join('')}</div>` : '';
                    const date = j.scraped_at ? new Date(j.scraped_at).toLocaleDateString('es-CO') : '-';
                    const urlHtml = j.url ? `<div class="job-url"><a href="${j.url}" target="_blank" rel="noopener">Ver oferta &#8599;</a></div>` : '';
                    card.innerHTML = `
                        <div class="job-header">
                            <div>
                                <div class="job-title">${j.title||'-'}</div>
                                <div class="job-company">${j.company||'-'}</div>
                                ${badgesHtml}
                            </div>
                            ${urlHtml}
                        </div>
                        <div class="job-details">
                            <div class="detail-item">
                                <span class="detail-label">Ubicación</span>
                                <span class="detail-value">${j.location||'-'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Fuente</span>
                                <span class="detail-value">${j.source||'-'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Tipo</span>
                                <span class="detail-value">${j.job_type||'-'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Salario</span>
                                <span class="detail-value">${j.salary||'-'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Fecha de extracción</span>
                                <span class="detail-value">${date}</span>
                            </div>
                        </div>
                    `;
                    container.appendChild(card);
                });
            } catch (e) {
                empty.textContent = 'Error al cargar resultados.';
                empty.style.display = 'block';
            }
        })();
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
            save_csv = params.get("save_csv", ["false"])[0].lower() == "true"

            jobs = run_scraper(keyword, source, limit=limit)

            json_filename = f"jobs_{keyword.replace(' ', '_')}.json"
            json_filepath = save_to_json(jobs, json_filename)

            csv_filepath = ""
            if save_csv:
                csv_filename = f"jobs_{keyword.replace(' ', '_')}.csv"
                csv_filepath = save_to_csv(jobs, csv_filename)

            response = json.dumps({
                "count": len(jobs),
                "file": json_filepath,
                "csv_file": csv_filepath,
            })
            self._respond(200, response, "application/json")

        elif parsed.path == "/results":
            self._respond(200, RESULTS_HTML, "text/html; charset=utf-8")

        elif parsed.path == "/api/results":
            params = parse_qs(parsed.query)
            filename = params.get("file", [None])[0]
            data_dir = Path("data")
            if filename:
                filepath = data_dir / filename
                if filepath.exists() and filepath.suffix == ".json":
                    with open(filepath, "r", encoding="utf-8") as f:
                        jobs = json.load(f)
                else:
                    jobs = []
            else:
                json_files = sorted(data_dir.glob("jobs_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                if json_files:
                    with open(json_files[0], "r", encoding="utf-8") as f:
                        jobs = json.load(f)
                else:
                    jobs = []
            self._respond(200, json.dumps(jobs, ensure_ascii=False), "application/json")

        elif parsed.path == "/api/files":
            data_dir = Path("data")
            json_files = sorted(data_dir.glob("jobs_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            files_info = []
            for fp in json_files:
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        jobs = json.load(f)
                    count = len(jobs)
                except Exception:
                    count = 0
                stat = fp.stat()
                files_info.append({
                    "name": fp.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "count": count,
                })
            self._respond(200, json.dumps(files_info, ensure_ascii=False), "application/json")

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
