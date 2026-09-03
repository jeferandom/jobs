"""Proveedor de autenticación de CompuTrabajo vía email/password."""

import logging
import threading

from playwright.sync_api import sync_playwright, Browser, BrowserContext

from src.auth.base import AuthProvider, LoginStatus
from src.auth.session_manager import SessionManager

logger = logging.getLogger(__name__)

LOGIN_URL = "https://candidato.co.computrabajo.com/acceso/"
SUCCESS_URL_MARKER = "candidate"
LOGIN_URL_MARKER = "acceso"
POLL_INTERVAL_MS = 1000
STEP_TIMEOUT_MS = 8000


class ComputrabajoCredentialsProvider(AuthProvider):
    """Login automatizado con email/password para CompuTrabajo.

    Flujo de dos pasos:
      1. Ingresa email → clic "Continuar"
      2. Ingresa contraseña → clic "Iniciar sesión"
    Guarda storage_state completo al detectar éxito.
    """

    def __init__(self) -> None:
        super().__init__()
        self._session_mgr = SessionManager()
        self._cancel_event = threading.Event()
        self._browser: Browser | None = None
        self._email: str | None = None
        self._password: str | None = None

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
        if self.get_status() == LoginStatus.IN_PROGRESS:
            return False
        self._set_status(LoginStatus.IN_PROGRESS)
        thread = threading.Thread(target=self._run_login, daemon=True)
        thread.start()
        return True

    def start_login_with_credentials(self, email: str, password: str) -> bool:
        """Inicia login automático con credenciales (sin ventana visible)."""
        if self.get_status() == LoginStatus.IN_PROGRESS:
            return False
        self._email = email
        self._password = password
        self._set_status(LoginStatus.IN_PROGRESS)
        thread = threading.Thread(target=self._run_credentials_login, daemon=True)
        thread.start()
        return True

    def cancel(self) -> None:
        self._cancel_event.set()
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass

    def _is_login_success(self, page) -> bool:
        """Detecta login exitoso por URL o presencia de elementos del dashboard."""
        try:
            url = page.url
            if SUCCESS_URL_MARKER in url and LOGIN_URL_MARKER not in url:
                return True
            if page.query_selector("nav.user-menu, .user-avatar, [data-user]"):
                return True
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # Flujo manual (ventana visible, el usuario ingresa credenciales)
    # ------------------------------------------------------------------

    def _run_login(self) -> None:
        try:
            with sync_playwright() as p:
                self._browser = p.chromium.launch(headless=False)
                context: BrowserContext = self._browser.new_context()
                page = context.new_page()

                try:
                    page.goto(self.login_url)
                except Exception:
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
                        if self._is_login_success(page):
                            storage_state = context.storage_state()
                            self._session_mgr.save(self.name, storage_state)
                            self._set_status(LoginStatus.SUCCESS)
                            return
                    except Exception:
                        self._set_status(LoginStatus.CANCELLED)
                        return

                    page.wait_for_timeout(POLL_INTERVAL_MS)
                    elapsed_ms += POLL_INTERVAL_MS

                self._set_status(LoginStatus.TIMEOUT)

        except Exception as e:
            if self._cancel_event.is_set():
                self._set_status(LoginStatus.CANCELLED)
            else:
                logger.error(f"Error en login manual de {self.name}: {e}")
                self._set_status(LoginStatus.ERROR, str(e))
        finally:
            self._close_browser()

    # ------------------------------------------------------------------
    # Flujo automático con credenciales (headless, sin ventana)
    # ------------------------------------------------------------------

    def _run_credentials_login(self) -> None:
        try:
            with sync_playwright() as p:
                self._browser = p.chromium.launch(headless=True)
                context: BrowserContext = self._browser.new_context(
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                try:
                    page.goto(self.login_url, wait_until="networkidle", timeout=STEP_TIMEOUT_MS)
                except Exception as e:
                    self._set_status(LoginStatus.ERROR, f"No se pudo cargar la página: {e}")
                    return

                # --- Paso 1: Email ---
                try:
                    # Esperar a que el formulario cargue completamente
                    page.wait_for_timeout(2000)

                    # Buscar el campo de email con múltiples selectores
                    email_input = page.query_selector("#Email") or page.query_selector("input[type='email']")
                    if not email_input:
                        email_input = page.wait_for_selector("input[type='email'], #Email", timeout=STEP_TIMEOUT_MS)

                    email_input.fill(self._email)
                    page.wait_for_timeout(500)

                    # Buscar botón de continuar
                    continue_btn = page.query_selector("#continueWithMailButton") or page.query_selector("button:has-text('Continuar')")
                    if not continue_btn:
                        continue_btn = page.wait_for_selector("#continueWithMailButton", timeout=STEP_TIMEOUT_MS)

                    continue_btn.click()
                except Exception as e:
                    self._set_status(LoginStatus.ERROR, f"Error en paso email: {e}")
                    return

                # --- Paso 2: Contraseña ---
                try:
                    # Esperar a que aparezca el campo de contraseña
                    page.wait_for_timeout(1000)

                    password_input = page.query_selector("#password") or page.query_selector("input[type='password']")
                    if not password_input:
                        password_input = page.wait_for_selector("input[type='password'], #password", timeout=STEP_TIMEOUT_MS)

                    password_input.fill(self._password)
                    page.wait_for_timeout(500)

                    # Buscar botón de enviar
                    submit_btn = page.query_selector("#btnSubmitPass") or page.query_selector("button:has-text('Iniciar sesión')")
                    if not submit_btn:
                        submit_btn = page.wait_for_selector("#btnSubmitPass", timeout=STEP_TIMEOUT_MS)

                    submit_btn.click()
                except Exception as e:
                    self._set_status(LoginStatus.ERROR, f"Error en paso contraseña: {e}")
                    return

                # --- Esperar resultado ---
                try:
                    page.wait_for_function(
                        f"""() => {{
                            const url = window.location.href;
                            const hasError = document.querySelector('.box_error:not(.hide), .field-validation-error');
                            const hasSuccess = url.includes('{SUCCESS_URL_MARKER}') && !url.includes('{LOGIN_URL_MARKER}');
                            return hasSuccess || hasError;
                        }}""",
                        timeout=STEP_TIMEOUT_MS,
                    )
                except Exception:
                    pass

                if self._is_login_success(page):
                    storage_state = context.storage_state()
                    self._session_mgr.save(self.name, storage_state)
                    self._set_status(LoginStatus.SUCCESS)
                else:
                    error_text = page.evaluate(
                        """() => {
                            const el = document.querySelector(
                                '.box_error:not(.hide), .field-validation-error, .validation-summary-errors'
                            );
                            return el ? el.textContent.trim() : null;
                        }"""
                    )
                    msg = error_text or "Credenciales incorrectas o captcha requerido"
                    self._set_status(LoginStatus.ERROR, msg)

        except Exception as e:
            if self._cancel_event.is_set():
                self._set_status(LoginStatus.CANCELLED)
            else:
                logger.error(f"Error en login de credenciales de {self.name}: {e}")
                self._set_status(LoginStatus.ERROR, str(e))
        finally:
            self._close_browser()

    def _close_browser(self) -> None:
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
