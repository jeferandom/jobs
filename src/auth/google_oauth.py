"""Proveedor de autenticación de CompuTrabajo vía Google OAuth (login manual)."""

import logging
import threading

from playwright.sync_api import sync_playwright, Browser, BrowserContext

from src.auth.base import AuthProvider, LoginStatus
from src.auth.session_manager import SessionManager

logger = logging.getLogger(__name__)

LOGIN_URL = "https://candidato.co.computrabajo.com/acceso/"
SUCCESS_URL_MARKER = "candidate/match"
POLL_INTERVAL_MS = 1000


class ComputrabajoOAuthProvider(AuthProvider):
    """Login manual con Google para CompuTrabajo usando Playwright.

    Abre un navegador visible, el usuario hace login manualmente y
    al detectar la URL de éxito guarda el storage_state completo
    (cookies + localStorage) para reutilizar la sesión.
    """

    def __init__(self) -> None:
        super().__init__()
        self._session_mgr = SessionManager()
        self._cancel_event = threading.Event()
        self._browser: Browser | None = None

    @property
    def name(self) -> str:
        return "computrabajo"

    @property
    def login_url(self) -> str:
        return LOGIN_URL

    @property
    def success_url_contains(self) -> str:
        return SUCCESS_URL_MARKER

    def start_login(self) -> bool:
        """Inicia el login en un hilo daemon. False si ya hay uno en progreso."""
        if self.get_status() == LoginStatus.IN_PROGRESS:
            logger.warning(f"Login ya en progreso para {self.name}")
            return False

        self._cancel_event.clear()
        self._set_status(LoginStatus.IN_PROGRESS)

        thread = threading.Thread(target=self._run_login, daemon=True)
        thread.start()
        return True

    def cancel(self) -> None:
        """Solicita cancelar el login (cierra el navegador)."""
        self._cancel_event.set()
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass

    def _run_login(self) -> None:
        """Ejecuta el flujo de login. Corre en hilo daemon."""
        try:
            with sync_playwright() as p:
                self._browser = p.chromium.launch(headless=False)
                context: BrowserContext = self._browser.new_context()
                page = context.new_page()

                try:
                    page.goto(self.login_url)
                except Exception:
                    # Navegador cerrado por cancel()
                    if self._cancel_event.is_set():
                        self._set_status(LoginStatus.CANCELLED)
                    else:
                        self._set_status(LoginStatus.ERROR, "No se pudo abrir la página")
                    return

                elapsed_ms = 0
                timeout_ms = self.timeout_seconds * 1000

                while elapsed_ms < timeout_ms:
                    if self._cancel_event.is_set():
                        self._set_status(LoginStatus.CANCELLED)
                        return

                    try:
                        if self.success_url_contains in page.url:
                            storage_state = context.storage_state()
                            self._session_mgr.save(self.name, storage_state)
                            self._set_status(LoginStatus.SUCCESS)
                            return
                    except Exception:
                        # Página cerrada por el usuario
                        self._set_status(LoginStatus.CANCELLED)
                        return

                    page.wait_for_timeout(POLL_INTERVAL_MS)
                    elapsed_ms += POLL_INTERVAL_MS

                self._set_status(LoginStatus.TIMEOUT)

        except Exception as e:
            # Si el navegador fue cerrado por cancel(), no es un error
            if self._cancel_event.is_set():
                self._set_status(LoginStatus.CANCELLED)
            else:
                logger.error(f"Error en login de {self.name}: {e}")
                self._set_status(LoginStatus.ERROR, str(e))

        finally:
            if self._browser:
                try:
                    self._browser.close()
                except Exception:
                    pass
                self._browser = None
