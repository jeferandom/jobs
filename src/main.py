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
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scrapers.computrabajo import ComputrabajoScraper
from src.scrapers.computrabajo_auth import ComputrabajoAuthScraper
from src.scrapers.base import JobSource, SessionExpiredError
from src.models.job import Job
from src.auth import SessionManager, ComputrabajoOAuthProvider
from src.auth.credentials import ComputrabajoCredentialsProvider
from src.auth.base import AuthProvider, LoginStatus
from src.analysis.wordcloud_gen import generate_wordcloud

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# =====================
# Auth providers
# =====================

_session_mgr = SessionManager()
_oauth_provider = ComputrabajoOAuthProvider()
_credentials_provider = ComputrabajoCredentialsProvider()
_auth_providers: dict[str, AuthProvider] = {
    "computrabajo": _oauth_provider,
}

# =====================
# Scrapers
# =====================


def get_scrapers() -> list[JobSource]:
    """Retorna la lista de adaptadores disponibles."""
    return [
        ComputrabajoScraper(),
        ComputrabajoAuthScraper(),
    ]


def run_scraper(keyword: str, source_name: str | None = None, limit: int = 100) -> list[Job]:
    """Ejecuta el scraper para la palabra clave y fuente indicadas.

    Solo incluye fuentes públicas (no requieren auth), salvo que se
    pida explícitamente una fuente autenticada.
    """
    scrapers = get_scrapers()

    if source_name:
        scrapers = [s for s in scrapers if s.name == source_name]
        if not scrapers:
            logger.error(f"Fuente no encontrada: {source_name}")
            return []
    else:
        scrapers = [s for s in scrapers if not s.requires_auth]

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
        .auth-section { margin-bottom: 1.5rem; padding: 1rem; background: #f8f9fa; border-radius: 8px; border: 1px solid #e3e3e3; }
        .auth-section h3 { font-size: 0.9rem; margin-bottom: 0.75rem; color: #333; }
        .auth-row { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0; }
        .auth-name { flex: 1; font-size: 0.85rem; font-weight: 600; }
        .auth-status { font-size: 0.75rem; color: #888; }
        .auth-status.success { color: #28a745; }
        .auth-status.in-progress { color: #4361ee; }
        .auth-status.error { color: #dc3545; }
        .auth-btn { padding: 0.35rem 0.75rem; background: #4361ee; color: white; border: none; border-radius: 6px; font-size: 0.75rem; cursor: pointer; width: auto; }
        .auth-btn:hover:not(:disabled) { background: #3a56d4; }
        .auth-btn:disabled { background: #aaa; cursor: wait; }
        .auth-btn.connected { background: #28a745; }
        .auth-btn.applied-btn { background: #9b59b6; }
        .auth-btn.applied-btn:hover { background: #8e44ad; }
        .modal { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
        .modal-content { background: white; padding: 2rem; border-radius: 12px; width: 90%; max-width: 400px; position: relative; }
        .modal-close { position: absolute; top: 1rem; right: 1rem; font-size: 1.5rem; cursor: pointer; color: #666; }
        .modal-close:hover { color: #333; }
        .modal-tabs { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; border-bottom: 1px solid #eee; padding-bottom: 0.5rem; }
        .tab-btn { flex: 1; padding: 0.5rem; background: none; border: none; cursor: pointer; font-size: 0.9rem; color: #666; border-radius: 6px 6px 0 0; }
        .tab-btn.active { color: #4361ee; border-bottom: 2px solid #4361ee; font-weight: 600; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .field { margin-bottom: 1rem; }
        .field label { display: block; margin-bottom: 0.25rem; font-weight: 600; font-size: 0.85rem; color: #333; }
        .field input { width: 100%; padding: 0.6rem; border: 1px solid #ddd; border-radius: 6px; font-size: 1rem; }
        .error-msg { color: #dc3545; font-size: 0.85rem; margin-bottom: 1rem; padding: 0.5rem; background: #f8d7da; border-radius: 6px; }
        .modal-hint { color: #666; font-size: 0.85rem; margin-bottom: 1rem; text-align: center; }
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

            <div class="auth-section">
                <h3>Fuentes con login</h3>
                <div class="auth-row">
                    <span class="auth-name">Computrabajo</span>
                    <span class="auth-status" id="auth-status-computrabajo">Verificando...</span>
                    <button class="auth-btn" id="auth-btn-computrabajo"
                            onclick="showLoginModal()">Iniciar sesión</button>
                </div>
                <div class="auth-row">
                    <span class="auth-name">InfoJobs</span>
                    <span class="auth-status success">Público</span>
                </div>
                <button class="auth-btn applied-btn" id="btn-applied"
                        onclick="window.location.href='/applied'" disabled>Mis postulaciones</button>
            </div>

            <!-- Modal de login -->
            <div id="loginModal" class="modal" style="display:none;">
                <div class="modal-content">
                    <span class="modal-close" onclick="closeLoginModal()">&times;</span>
                    <h3>Iniciar sesión en CompuTrabajo</h3>
                    <div class="modal-tabs">
                        <button class="tab-btn active" onclick="showTab('credentials')">Email y contraseña</button>
                        <button class="tab-btn" onclick="showTab('google')">Google</button>
                    </div>
                    <div id="tab-credentials" class="tab-content active">
                        <form id="loginForm" onsubmit="return credentialsLogin(event)">
                            <div class="field">
                                <label for="login-email">Email</label>
                                <input type="email" id="login-email" required placeholder="tu@email.com">
                            </div>
                            <div class="field">
                                <label for="login-password">Contraseña</label>
                                <input type="password" id="login-password" required placeholder="••••••••">
                            </div>
                            <div id="login-error" class="error-msg" style="display:none;"></div>
                            <button type="submit" class="auth-btn" id="btn-credentials-login">Iniciar sesión</button>
                        </form>
                    </div>
                    <div id="tab-google" class="tab-content">
                        <p class="modal-hint">Se abrirá una ventana del navegador para autenticarte con Google.</p>
                        <button class="auth-btn" onclick="startGoogleLogin()">Continuar con Google</button>
                    </div>
                </div>
            </div>

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
        // =====================
        // Auth
        // =====================

        async function checkAuthStatus() {
            try {
                const resp = await fetch('/api/auth/status');
                const statuses = await resp.json();
                for (const [provider, state] of Object.entries(statuses)) {
                    updateAuthUI(provider, state);
                }
            } catch (e) {
                console.error('Error verificando auth:', e);
            }
        }

        function updateAuthUI(provider, state) {
            const btn = document.getElementById(`auth-btn-${provider}`);
            const status = document.getElementById(`auth-status-${provider}`);
            const appliedBtn = document.getElementById('btn-applied');
            if (!btn || !status) return;

            btn.disabled = false;
            status.className = 'auth-status';

            switch (state) {
                case 'connected':
                    btn.textContent = 'Cerrar sesión';
                    btn.classList.add('connected');
                    btn.onclick = () => logoutAuth(provider);
                    status.textContent = 'Conectado';
                    status.classList.add('success');
                    if (appliedBtn) appliedBtn.disabled = false;
                    break;
                case 'in_progress':
                    btn.textContent = 'Cancelar';
                    btn.onclick = () => cancelAuth(provider);
                    status.textContent = 'Login en curso...';
                    status.classList.add('in-progress');
                    break;
                case 'cancelled':
                case 'timeout':
                    btn.textContent = 'Iniciar sesión';
                    btn.onclick = () => showLoginModal();
                    status.textContent = state === 'timeout' ? 'Tiempo agotado' : 'Cancelado';
                    status.classList.add('error');
                    if (appliedBtn) appliedBtn.disabled = true;
                    break;
                case 'error':
                    btn.textContent = 'Iniciar sesión';
                    btn.onclick = () => showLoginModal();
                    status.textContent = 'Error';
                    status.classList.add('error');
                    if (appliedBtn) appliedBtn.disabled = true;
                    break;
                default:
                    btn.textContent = 'Iniciar sesión';
                    btn.onclick = () => showLoginModal();
                    status.textContent = 'No conectado';
                    if (appliedBtn) appliedBtn.disabled = true;
            }
        }

        async function startAuth(provider) {
            updateAuthUI(provider, 'in_progress');
            await fetch(`/api/auth/start/${provider}`, { method: 'POST' });
            pollAuthStatus(provider);
        }

        async function cancelAuth(provider) {
            await fetch(`/api/auth/cancel/${provider}`, { method: 'POST' });
            updateAuthUI(provider, 'cancelled');
        }

        async function logoutAuth(provider) {
            await fetch(`/api/auth/logout/${provider}`, { method: 'POST' });
            updateAuthUI(provider, 'disconnected');
        }

        function pollAuthStatus(provider) {
            const interval = setInterval(async () => {
                const resp = await fetch(`/api/auth/check/${provider}`);
                const data = await resp.json();
                updateAuthUI(provider, data.status);
                if (data.status !== 'in_progress') {
                    clearInterval(interval);
                    closeLoginModal();
                    if (data.error) {
                        document.getElementById('login-error').textContent = data.error;
                        document.getElementById('login-error').style.display = 'block';
                    }
                }
            }, 2000);
        }

        // =====================
        // Login Modal
        // =====================

        function showLoginModal() {
            document.getElementById('loginModal').style.display = 'flex';
            showTab('credentials');
        }

        function closeLoginModal() {
            document.getElementById('loginModal').style.display = 'none';
            document.getElementById('login-error').style.display = 'none';
        }

        function showTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById(`tab-${tab}`).classList.add('active');
            event.target.classList.add('active');
        }

        async function credentialsLogin(e) {
            e.preventDefault();
            const email = document.getElementById('login-email').value;
            const password = document.getElementById('login-password').value;
            const errorDiv = document.getElementById('login-error');
            const btn = document.getElementById('btn-credentials-login');

            errorDiv.style.display = 'none';
            btn.disabled = true;
            btn.textContent = 'Ingresando...';

            try {
                const resp = await fetch('/api/auth/login/computrabajo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });
                const data = await resp.json();

                if (resp.ok) {
                    updateAuthUI('computrabajo', 'in_progress');
                    pollAuthStatus('computrabajo');
                } else {
                    errorDiv.textContent = data.error || 'Error al iniciar sesión';
                    errorDiv.style.display = 'block';
                    btn.disabled = false;
                    btn.textContent = 'Iniciar sesión';
                }
            } catch (err) {
                errorDiv.textContent = 'Error de conexión: ' + err.message;
                errorDiv.style.display = 'block';
                btn.disabled = false;
                btn.textContent = 'Iniciar sesión';
            }
            return false;
        }

        async function startGoogleLogin() {
            closeLoginModal();
            startAuth('computrabajo');
        }

        async function fetchApplied() {
            const result = document.getElementById('result');
            result.className = '';
            result.textContent = 'Cargando postulaciones...';
            result.style.display = 'block';
            try {
                const resp = await fetch('/api/applied/computrabajo');
                const data = await resp.json();
                if (!resp.ok) {
                    result.className = 'error';
                    result.textContent = data.error || 'Error al cargar postulaciones';
                    return;
                }
                result.className = 'success';
                result.textContent = `${data.count} postulaciones guardadas en ${data.file}`;
                loadFiles();
            } catch (e) {
                result.className = 'error';
                result.textContent = 'Error: ' + e.message;
            }
        }

        // =====================
        // Files / Search
        // =====================

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

        checkAuthStatus();
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
        .header-actions { margin-left: auto; display: flex; gap: 0.5rem; }
        .wordcloud-btn { padding: 0.5rem 1rem; background: #9b59b6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; text-decoration: none; }
        .wordcloud-btn:hover { background: #8e44ad; }
        .wordcloud-btn:disabled { background: #aaa; cursor: not-allowed; }
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
        .job-actions { display: flex; gap: 0.5rem; margin-top: 1rem; }
        .desc-btn { padding: 0.4rem 0.8rem; background: #17a2b8; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.8rem; }
        .desc-btn:hover { background: #138496; }
        .desc-btn:disabled { background: #aaa; cursor: not-allowed; }
        .desc-btn.loading { background: #6c757d; }
        .job-description { margin-top: 1rem; padding: 1rem; background: #f8f9fa; border-radius: 8px; font-size: 0.85rem; line-height: 1.5; color: #333; display: none; white-space: pre-wrap; }
        .job-description.visible { display: block; }
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
        <div class="header-actions">
            <button class="wordcloud-btn" id="wordcloudBtn" onclick="showWordcloud()" disabled>&#9729; Nube de Palabras</button>
        </div>
    </div>
    <div class="jobs-container" id="jobsContainer">
        <div class="empty" id="empty">No hay resultados para mostrar.</div>
    </div>

    <script>
        let currentFile = null;

        async function showWordcloud() {
            const btn = document.getElementById('wordcloudBtn');
            btn.disabled = true;
            btn.textContent = 'Generando...';
            try {
                const params = new URLSearchParams(window.location.search);
                const file = params.get('file');
                const url = file ? `/api/wordcloud?file=${encodeURIComponent(file)}` : '/api/wordcloud';
                const resp = await fetch(url);
                if (!resp.ok) {
                    const err = await resp.json();
                    alert(err.error || 'Error al generar nube');
                    return;
                }
                const blob = await resp.blob();
                const imgUrl = URL.createObjectURL(blob);
                const win = window.open('', '_blank');
                win.document.write(`<html><head><title>Nube de Palabras</title><style>body{margin:0;display:flex;justify-content:center;align-items:center;min-height:100vh;background:#f0f2f5;}img{max-width:100%;height:auto;box-shadow:0 2px 8px rgba(0,0,0,0.1);border-radius:8px;}</style></head><body><img src="${imgUrl}"></body></html>`);
            } catch (e) {
                alert('Error: ' + e.message);
            } finally {
                btn.disabled = false;
                btn.textContent = '&#9729; Nube de Palabras';
            }
        }

        async function fetchDescription(index, btn) {
            btn.disabled = true;
            btn.classList.add('loading');
            btn.textContent = 'Cargando...';
            try {
                const params = new URLSearchParams(window.location.search);
                const file = params.get('file');
                const url = file
                    ? `/api/job/${index}/description?file=${encodeURIComponent(file)}`
                    : `/api/job/${index}/description`;
                const resp = await fetch(url);
                const data = await resp.json();
                const descEl = btn.closest('.job-card').querySelector('.job-description');
                if (data.description) {
                    descEl.textContent = data.description;
                    descEl.classList.add('visible');
                    btn.textContent = 'Descripcion cargada';
                    btn.style.background = '#28a745';
                } else {
                    descEl.textContent = 'No se pudo obtener la descripcion.';
                    descEl.classList.add('visible');
                    btn.textContent = 'Sin descripcion';
                    btn.style.background = '#dc3545';
                }
            } catch (e) {
                btn.textContent = 'Error';
                btn.style.background = '#dc3545';
            }
        }

        (async () => {
            const container = document.getElementById('jobsContainer');
            const empty = document.getElementById('empty');
            const countEl = document.getElementById('count');
            const fileLabel = document.getElementById('fileLabel');
            const wordcloudBtn = document.getElementById('wordcloudBtn');
            const params = new URLSearchParams(window.location.search);
            const file = params.get('file');
            currentFile = file;
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
                wordcloudBtn.disabled = false;
                jobs.forEach((j, idx) => {
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
                    const descBtnHtml = j.url ? `<button class="desc-btn" onclick="fetchDescription(${idx}, this)">Ver descripcion</button>` : '';
                    const hasDesc = j.description ? 'visible' : '';
                    const descText = j.description || '';
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
                                <span class="detail-label">Ubicacion</span>
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
                                <span class="detail-label">Fecha de extraccion</span>
                                <span class="detail-value">${date}</span>
                            </div>
                        </div>
                        <div class="job-actions">${descBtnHtml}</div>
                        <div class="job-description ${hasDesc}">${descText}</div>
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


APPLIED_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mis Postulaciones - Jobs Scraper</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; background: #f0f2f5; padding: 2rem; }
        .header { max-width: 1000px; margin: 0 auto 1.5rem; display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
        h1 { font-size: 1.5rem; color: #1a1a2e; }
        .back-btn { padding: 0.5rem 1rem; background: #4361ee; color: white; border: none; border-radius: 6px; cursor: pointer; text-decoration: none; font-size: 0.9rem; }
        .back-btn:hover { background: #3a56d4; }
        .count { color: #666; font-size: 0.9rem; }
        .jobs-container { max-width: 1000px; margin: 0 auto; display: flex; flex-direction: column; gap: 1rem; }
        .job-card { background: white; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); padding: 1.25rem 1.5rem; transition: box-shadow 0.15s, transform 0.15s; }
        .job-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); transform: translateY(-1px); }
        .job-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
        .job-title { font-size: 1.1rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0.25rem; }
        .job-company { font-size: 0.95rem; color: #4361ee; font-weight: 600; }
        .job-badges { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.5rem; }
        .badge { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.2rem 0.55rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
        .badge.applied { background: #9b59b6; color: white; }
        .badge.type { background: #e9ecef; color: #495057; }
        .job-details { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem 1.5rem; margin-top: 1rem; font-size: 0.85rem; }
        .detail-item { display: flex; flex-direction: column; gap: 0.15rem; }
        .detail-label { color: #888; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.3px; }
        .detail-value { color: #333; font-weight: 500; }
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
        <h1>Mis Postulaciones</h1>
        <span class="count" id="count"></span>
    </div>
    <div class="jobs-container" id="jobsContainer">
        <div class="empty" id="empty">No hay postulaciones para mostrar.</div>
    </div>

    <script>
        (async () => {
            const container = document.getElementById('jobsContainer');
            const empty = document.getElementById('empty');
            const countEl = document.getElementById('count');
            try {
                const resp = await fetch('/api/applied/list');
                const jobs = await resp.json();
                if (!jobs.length) { empty.style.display = 'block'; return; }
                empty.style.display = 'none';
                countEl.textContent = `${jobs.length} postulaciones`;
                jobs.forEach((j) => {
                    const card = document.createElement('div');
                    card.className = 'job-card';
                    const badges = ['<span class="badge applied">Postulado</span>'];
                    if (j.job_type) badges.push(`<span class="badge type">${j.job_type}</span>`);
                    const badgesHtml = `<div class="job-badges">${badges.join('')}</div>`;
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
                                <span class="detail-label">Ubicacion</span>
                                <span class="detail-value">${j.location||'-'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Fuente</span>
                                <span class="detail-value">${j.source||'-'}</span>
                            </div>
                        </div>
                    `;
                    container.appendChild(card);
                });
            } catch (e) {
                empty.textContent = 'Error al cargar postulaciones.';
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
        path_parts = [p for p in parsed.path.split("/") if p]

        if parsed.path == "/":
            sources_options = "".join(
                f'<option value="{s.name}">{s.name.capitalize()}</option>'
                for s in get_scrapers()
            )
            page = HTML_PAGE.replace("__SOURCES__", sources_options)
            self._respond(200, page, "text/html; charset=utf-8")

        elif parsed.path == "/api/auth/status":
            statuses = {}
            for name, provider in _auth_providers.items():
                if _session_mgr.exists(name):
                    statuses[name] = "connected"
                else:
                    statuses[name] = "disconnected"
            self._respond(200, json.dumps(statuses), "application/json")

        elif len(path_parts) == 4 and path_parts[0] == "api" and path_parts[1] == "auth" and path_parts[2] == "check":
            self._handle_auth_check(path_parts[3])

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

        elif len(path_parts) == 4 and path_parts[0] == "api" and path_parts[1] == "job" and path_parts[3] == "description":
            self._handle_job_description(path_parts[2], parsed.query)

        elif parsed.path == "/api/wordcloud":
            self._handle_wordcloud(parsed.query)

        elif parsed.path == "/applied":
            self._respond(200, APPLIED_HTML, "text/html; charset=utf-8")

        elif parsed.path == "/api/applied/list":
            self._handle_applied_list()

        elif len(path_parts) == 3 and path_parts[0] == "api" and path_parts[1] == "applied":
            self._handle_applied(path_parts[2])

        else:
            self._respond(404, "Not found", "text/plain")

    def do_POST(self) -> None:
        """Rutas POST: inicio, cancelación y cierre de login."""
        parsed = urlparse(self.path)
        path_parts = [p for p in parsed.path.split("/") if p]

        if len(path_parts) == 4 and path_parts[0] == "api" and path_parts[1] == "auth":
            action = path_parts[2]
            provider_name = path_parts[3]

            if action == "start":
                self._handle_auth_start(provider_name)
            elif action == "login":
                self._handle_auth_login(provider_name)
            elif action == "cancel":
                self._handle_auth_cancel(provider_name)
            elif action == "logout":
                self._handle_auth_logout(provider_name)
            else:
                self._respond(404, "Not found", "text/plain")
        else:
            self._respond(404, "Not found", "text/plain")

    def _handle_auth_start(self, provider_name: str) -> None:
        """Inicia el login de un proveedor en hilo daemon (ventana manual)."""
        provider = _auth_providers.get(provider_name)
        if not provider:
            self._respond(404, json.dumps({"error": "Proveedor no soportado"}), "application/json")
            return

        started = provider.start_login()
        if started:
            self._respond(200, json.dumps({"status": "in_progress"}), "application/json")
        else:
            self._respond(409, json.dumps({"error": "Login ya en progreso"}), "application/json")

    def _handle_auth_login(self, provider_name: str) -> None:
        """Login automático con credenciales email/password."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._respond(400, json.dumps({"error": "JSON inválido"}), "application/json")
            return

        email = data.get("email", "").strip()
        password = data.get("password", "").strip()

        if not email or not password:
            self._respond(400, json.dumps({"error": "Email y contraseña son requeridos"}), "application/json")
            return

        if provider_name == "computrabajo":
            started = _credentials_provider.start_login_with_credentials(email, password)
        else:
            self._respond(404, json.dumps({"error": "Proveedor no soportado"}), "application/json")
            return

        if started:
            self._respond(200, json.dumps({"status": "in_progress"}), "application/json")
        else:
            self._respond(409, json.dumps({"error": "Login ya en progreso"}), "application/json")

    def _handle_auth_cancel(self, provider_name: str) -> None:
        """Cancela el login en progreso."""
        provider = _auth_providers.get(provider_name)
        if not provider:
            self._respond(404, json.dumps({"error": "Proveedor no soportado"}), "application/json")
            return
        provider.cancel()
        self._respond(200, json.dumps({"status": "cancelled"}), "application/json")

    def _handle_auth_logout(self, provider_name: str) -> None:
        """Elimina la sesión guardada."""
        deleted = _session_mgr.delete(provider_name)
        if deleted:
            provider = _auth_providers.get(provider_name)
            if provider:
                provider._set_status(LoginStatus.IDLE)
            self._respond(200, json.dumps({"status": "disconnected"}), "application/json")
        else:
            self._respond(404, json.dumps({"error": "No hay sesión guardada"}), "application/json")

    def _handle_auth_check(self, provider_name: str) -> None:
        """Retorna el estado actual del login para un proveedor.

        Revisa tanto el provider OAuth como el de credenciales.
        """
        if provider_name == "computrabajo":
            providers_to_check = [_oauth_provider, _credentials_provider]
        else:
            provider = _auth_providers.get(provider_name)
            providers_to_check = [provider] if provider else []

        if not providers_to_check:
            self._respond(404, json.dumps({"error": "Proveedor no soportado"}), "application/json")
            return

        # Si ya hay sesión guardada, reportar connected
        if _session_mgr.exists(provider_name):
            self._respond(200, json.dumps({"status": "connected"}), "application/json")
            return

        # Revisar el estado de los providers
        for provider in providers_to_check:
            status = provider.get_status()
            error = provider.get_error_message()

            if status == LoginStatus.SUCCESS:
                self._respond(200, json.dumps({"status": "connected"}), "application/json")
                return

            if status == LoginStatus.IN_PROGRESS:
                self._respond(200, json.dumps({"status": "in_progress"}), "application/json")
                return

            if status in (LoginStatus.TIMEOUT, LoginStatus.CANCELLED, LoginStatus.ERROR):
                body = {"status": status.value}
                if error:
                    body["error"] = error
                self._respond(200, json.dumps(body), "application/json")
                return

        self._respond(200, json.dumps({"status": "idle"}), "application/json")

    def _handle_applied(self, provider_name: str) -> None:
        """Scrapea y retorna las postulaciones del usuario."""
        if not _session_mgr.exists(provider_name):
            self._respond(
                401,
                json.dumps({"error": "login_required", "provider": provider_name}),
                "application/json",
            )
            return

        scraper = next((s for s in get_scrapers() if s.name == provider_name and s.requires_auth), None)
        if not scraper:
            self._respond(404, json.dumps({"error": "Proveedor no soportado"}), "application/json")
            return

        try:
            jobs = scraper.get_applied_jobs()
            filename = f"applied_{provider_name}.json"
            filepath = save_to_json(jobs, filename)
            self._respond(
                200,
                json.dumps({"count": len(jobs), "file": filepath}),
                "application/json",
            )
        except SessionExpiredError as e:
            self._respond(
                401,
                json.dumps({"error": "session_expired", "message": str(e)}),
                "application/json",
            )
        except Exception as e:
            logger.error(f"Error obteniendo postulaciones: {e}")
            self._respond(500, json.dumps({"error": str(e)}), "application/json")

    def _handle_applied_list(self) -> None:
        """Retorna las postulaciones guardadas en applied_computrabajo.json."""
        data_dir = Path("data")
        filepath = data_dir / "applied_computrabajo.json"
        if not filepath.exists():
            self._respond(200, json.dumps([], ensure_ascii=False), "application/json")
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                jobs = json.load(f)
            self._respond(200, json.dumps(jobs, ensure_ascii=False), "application/json")
        except Exception as e:
            logger.error(f"Error leyendo postulaciones: {e}")
            self._respond(500, json.dumps({"error": str(e)}), "application/json")

    def _handle_job_description(self, index_str: str, query_string: str) -> None:
        """Obtiene y guarda la descripcion de una oferta."""
        try:
            index = int(index_str)
        except ValueError:
            self._respond(400, json.dumps({"error": "Indice invalido"}), "application/json")
            return

        params = parse_qs(query_string)
        filename = params.get("file", [None])[0]
        data_dir = Path("data")

        if filename:
            filepath = data_dir / filename
        else:
            json_files = sorted(data_dir.glob("jobs_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            filepath = json_files[0] if json_files else None

        if not filepath or not filepath.exists():
            self._respond(404, json.dumps({"error": "Archivo no encontrado"}), "application/json")
            return

        with open(filepath, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        if index < 0 or index >= len(jobs):
            self._respond(400, json.dumps({"error": "Indice fuera de rango"}), "application/json")
            return

        job = jobs[index]

        if job.get("description"):
            self._respond(200, json.dumps({"description": job["description"]}, ensure_ascii=False), "application/json")
            return

        url = job.get("url")
        if not url:
            self._respond(200, json.dumps({"description": None}, ensure_ascii=False), "application/json")
            return

        scraper = ComputrabajoScraper()
        description = scraper.fetch_description(url)

        if description:
            jobs[index]["description"] = description
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(jobs, f, ensure_ascii=False, indent=2)
            logger.info(f"Descripcion guardada para oferta {index} en {filepath.name}")

        self._respond(200, json.dumps({"description": description}, ensure_ascii=False), "application/json")

    def _handle_wordcloud(self, query_string: str) -> None:
        """Genera y retorna la imagen de la nube de palabras."""
        params = parse_qs(query_string)
        filename = params.get("file", [None])[0]
        data_dir = Path("data")

        if filename:
            filepath = data_dir / filename
        else:
            json_files = sorted(data_dir.glob("jobs_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            filepath = json_files[0] if json_files else None

        if not filepath or not filepath.exists():
            self._respond(404, json.dumps({"error": "Archivo no encontrado"}), "application/json")
            return

        with open(filepath, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        output_path = str(data_dir / f"wordcloud_{filepath.stem}.png")
        result = generate_wordcloud(jobs, output_path=output_path)

        if not result:
            self._respond(404, json.dumps({"error": "No hay datos suficientes para generar la nube"}), "application/json")
            return

        with open(result, "rb") as f:
            image_data = f.read()

        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(image_data)))
        self.end_headers()
        self.wfile.write(image_data)

    def _respond(self, code: int, body: str, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        logger.info(f"HTTP {format % args}")


class ReusableHTTPServer(ThreadingHTTPServer):
    """Servidor HTTP multi-hilo para no bloquear durante logins largos."""

    allow_reuse_address = True
    daemon_threads = True


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
