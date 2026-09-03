# Arquitectura: Scraping Autenticado de Postulaciones

## Objetivo

Extender el proyecto para scrapear **ofertas postuladas** en portales que requieren login (CompuTrabajo vía email/password o Google OAuth), manteniendo compatibilidad con el scraping público por keyword.

## Decisiones clave

| Problema | Solución |
|---|---|
| `HTTPServer` de un solo hilo bloquea la UI durante el login | `ThreadingHTTPServer` |
| Guardar "solo cookies" no restaura sesión OAuth | `context.storage_state()` (cookies + localStorage) |
| `JobSource.search(keyword)` no modela "mis postulaciones" | Método opcional `get_applied_jobs()` |
| Login cancelado dejaba el hilo colgado | Timeout de 120s + estado `cancelled` |
| Google OAuth bloqueado por seguridad de Google | Soporte alternativo con credenciales email/password |
| `data/sessions/` no estaba en .gitignore | Agregado |

## Estructura

```
src/
├── auth/
│   ├── __init__.py
│   ├── base.py              # AuthProvider (ABC): login_url, detecta éxito, timeout
│   ├── session_manager.py   # storage_state save/load/exists en data/sessions/
│   ├── google_oauth.py      # Login manual con Google vía Playwright (hilo daemon)
│   └── credentials.py       # Login automatizado con email/password (headless)
├── scrapers/
│   ├── base.py              # JobSource + get_applied_jobs() opcional
│   ├── computrabajo.py      # Público (sin cambios)
│   └── computrabajo_auth.py # Postulaciones con sesión guardada
├── models/job.py            # Sin cambios
└── main.py                  # ThreadingHTTPServer + endpoints auth + UI con modal

data/
└── sessions/                # storage_state JSON (gitignored)
    └── computrabajo.json
```

## Proveedores de autenticación

### `AuthProvider` (src/auth/base.py)

```python
class AuthProvider(ABC):
    name: str                    # identificador, ej "computrabajo"
    login_url: str               # URL donde inicia el login
    success_url_contains: str    # subcadena de URL que indica login exitoso
    timeout_seconds: int = 120

    def start_login(self) -> bool: ...              # login manual (ventana visible)
    def get_status(self) -> LoginStatus: ...        # idle | in_progress | success | cancelled | timeout | error
    def cancel(self) -> None: ...                   # cierra navegador y cancela
```

### `ComputrabajoOAuthProvider` (src/auth/google_oauth.py)

- Abre ventana visible con Playwright
- Usuario hace login manual con Google
- Detecta éxito al llegar a URL que contiene `candidate`
- Guarda `storage_state` completo

### `ComputrabajoCredentialsProvider` (src/auth/credentials.py)

- Login automatizado en headless (sin ventana)
- Flujo de dos pasos:
  1. Ingresa email → clic "Continuar"
  2. Ingresa contraseña → clic "Iniciar sesión"
- Detecta errores del formulario (contraseña incorrecta, captcha)
- Método `start_login_with_credentials(email, password)`

### `SessionManager` (src/auth/session_manager.py)

```python
class SessionManager:
    def exists(provider) -> bool
    def save(provider, storage_state: dict) -> None
    def load(provider) -> dict | None        # para browser.new_context(storage_state=...)
    def delete(provider) -> None             # para cerrar sesión
```

## Scrapers

### `JobSource` extendido (src/scrapers/base.py)

```python
class JobSource(ABC):
    name: str
    requires_auth: bool = False

    def search(keyword, limit) -> list[Job]          # público
    def get_applied_jobs(self) -> list[Job]: ...     # opcional, solo fuentes auth
```

### `ComputrabajoAuthScraper` (src/scrapers/computrabajo_auth.py)

- Usa Playwright con `browser.new_context(storage_state=SessionManager.load("computrabajo"))`.
- Navega a `https://candidato.co.computrabajo.com/candidate/match`.
- Si la sesión expiró (redirect a login), lanza `SessionExpiredError`.
- Extrae: título, empresa, ubicación, url.
- Solo `get_applied_jobs()`; `search()` no aplica.

## Endpoints (main.py)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/auth/status` | Estado de cada proveedor: `connected`, `disconnected` |
| POST | `/api/auth/start/{provider}` | Login manual (ventana Playwright) |
| POST | `/api/auth/login/{provider}` | Login con credenciales `{email, password}` |
| POST | `/api/auth/cancel/{provider}` | Cancelar login en progreso |
| POST | `/api/auth/logout/{provider}` | Eliminar sesión guardada |
| GET | `/api/auth/check/{provider}` | Estado del login (para polling) |
| GET | `/api/applied/{provider}` | Scrapea postulaciones (requiere sesión) |

## Flujos de login

### Opción 1: Credenciales (recomendada)

```
Click "Iniciar sesión" → modal → pestaña "Email y contraseña"
  → ingresar email + contraseña → POST /api/auth/login/computrabajo
  → hilo daemon: playwright headless → login_url
    → Paso 1: fill #Email → click #continueWithMailButton
    → Paso 2: fill #password → click #btnSubmitPass
    → Detectar éxito o error
  → polling GET /api/auth/check/computrabajo cada 2s
    → success → "Conectado ✓"
    → error → mostrar mensaje ("Contraseña incorrecta", etc.)
```

### Opción 2: Google OAuth

```
Click "Iniciar sesión" → modal → pestaña "Google"
  → POST /api/auth/start/computrabajo
  → hilo daemon: playwright headless=False → login_url
  → usuario hace login con Google manualmente
  → polling GET /api/auth/check/computrabajo cada 2s
    → success → "Conectado ✓"
    → timeout (120s) → "Tiempo agotado"
    → ventana cerrada → "Cancelado"
```

## Flujo de scraping autenticado

```
Click "Mis postulaciones" → GET /api/applied/computrabajo
  → si no hay sesión → 401 {error: "login_required"}
  → si sesión expirada → 401 {error: "session_expired"}
  → ok → lista de Job + guarda data/applied_computrabajo.json
```

## Riesgos aceptados

- **Google OAuth puede ser bloqueado** por seguridad de Google. Mitigación: usar credenciales directas.
- **Captcha en login de credenciales**. Mitigación: detectar y reportar error al usuario.
- **403 Forbidden en headless**. Mitigación: anti-detección con User-Agent real, `--disable-blink-features=AutomationControlled`, y `navigator.webdriver = undefined`.
- **Cookies en disco** (JSON plano). Mitigación: `data/sessions/` en .gitignore.
- **Un login a la vez por proveedor**: el provider guarda su estado; un segundo intento rechaza si ya hay uno `in_progress`.

## Verificación

1. `pip install -r requirements.txt && playwright install chromium`
2. `python3 src/main.py --web` → panel auth muestra "No conectado"
3. Click "Iniciar sesión" → modal → ingresar email/contraseña → "Conectado ✓"
4. `data/sessions/computrabajo.json` existe
5. Click "Mis postulaciones" → lista con las ofertas postuladas
6. Re-ejecutar: sin login nuevo, usa la sesión guardada

## Estado

| Componente | Estado |
|---|---|
| Login con credenciales | ✅ Funcionando |
| Login con Google OAuth | ⚠️ Bloqueado por Google (usar credenciales) |
| Scraping público (search) | ✅ Funcionando |
| Scraping autenticado (postulaciones) | ✅ Funcionando |
| UI Web con modal auth | ✅ Funcionando |
