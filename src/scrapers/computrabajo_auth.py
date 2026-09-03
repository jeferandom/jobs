"""Scraper autenticado de CompuTrabajo: extrae las postulaciones del usuario."""

import logging
import time

from playwright.sync_api import sync_playwright, BrowserContext

from src.auth.session_manager import SessionManager
from src.models.job import Job
from src.scrapers.base import JobSource, SessionExpiredError

logger = logging.getLogger(__name__)

MATCH_URL = "https://candidato.co.computrabajo.com/candidate/match"
LOGIN_URL = "https://candidato.co.computrabajo.com/acceso/"
PAGE_LOAD_TIMEOUT_MS = 30000
SCROLL_PAUSE_S = 1.5
MAX_SCROLLS = 20

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


class ComputrabajoAuthScraper(JobSource):
    """Extrae las ofertas a las que el usuario está postulado en CompuTrabajo.

    Requiere una sesión guardada previamente (ver src/auth/credentials.py).
    """

    def __init__(self) -> None:
        self._session_mgr = SessionManager()

    @property
    def name(self) -> str:
        return "computrabajo"

    @property
    def requires_auth(self) -> bool:
        return True

    def search(self, keyword: str, limit: int = 100) -> list[Job]:
        """No aplica para la vista autenticada de postulaciones."""
        logger.warning(
            "search() no aplica al scraper autenticado; use get_applied_jobs()"
        )
        return []

    def get_applied_jobs(self) -> list[Job]:
        """Scrapea las postulaciones del usuario en candidate/match.

        Raises:
            SessionExpiredError: Si no hay sesión o está expirada.
        """
        storage_state = self._session_mgr.load(self.name)
        if storage_state is None:
            raise SessionExpiredError(
                f"No hay sesión guardada para {self.name}. Inicie sesión primero."
            )

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            context: BrowserContext = browser.new_context(
                storage_state=storage_state,
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 720},
                locale="es-CO",
            )

            # Inyectar script anti-detección antes de cada navigación
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)

            page = context.new_page()

            try:
                page.goto(MATCH_URL, timeout=PAGE_LOAD_TIMEOUT_MS)
                page.wait_for_load_state("networkidle", timeout=PAGE_LOAD_TIMEOUT_MS)

                if LOGIN_URL in page.url or "acceso" in page.url:
                    raise SessionExpiredError(
                        "La sesión expiró. Inicie sesión nuevamente."
                    )

                # Verificar si la página cargó contenido real
                body_text = page.evaluate("document.body.innerText")
                if "403 Forbidden" in body_text or len(body_text) < 100:
                    logger.warning(
                        "Posible bloqueo anti-bot. Intentando con scroll..."
                    )

                self._scroll_to_load_all(page)
                jobs = self._parse_applied_jobs(page)
                logger.info(f"Postulaciones extraídas: {len(jobs)}")
                return jobs

            finally:
                browser.close()

    def _scroll_to_load_all(self, page) -> None:
        """Hace scroll hasta que no carguen más resultados."""
        last_count = 0
        for _ in range(MAX_SCROLLS):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(SCROLL_PAUSE_S)

            count = page.evaluate(
                "document.querySelectorAll('article.box_offer').length"
            )
            if count == last_count:
                break
            last_count = count

    def _parse_applied_jobs(self, page) -> list[Job]:
        """Extrae las tarjetas de ofertas postuladas del DOM."""
        raw_jobs: list[dict] = page.evaluate(
            """() => {
                const cards = document.querySelectorAll('div.box[data-match]');
                return Array.from(cards).map(card => {
                    const titleEl = card.querySelector('h1');
                    // La empresa es el primer p.fc_base con mt5
                    const companyEl = card.querySelector('p.fc_base.mt5');
                    // La ubicación es el segundo p.fc_base (sin mt5)
                    const paragraphs = card.querySelectorAll('p.fc_base');
                    const locationEl = paragraphs.length > 1 ? paragraphs[1] : null;
                    // La URL está en el atributo data-shortcut-see-offer
                    const linkEl = card.querySelector('[data-shortcut-see-offer]');
                    const url = linkEl ? linkEl.getAttribute('data-shortcut-see-offer') : null;
                    
                    // Limpiar empresa: quitar rating "4,5" y espacios extra
                    let company = companyEl ? companyEl.textContent.trim() : 'N/A';
                    company = company.replace(/\\s+\\d+,\\d+$/, '').trim();
                    
                    return {
                        title: titleEl ? titleEl.textContent.trim() : 'N/A',
                        url: url,
                        company: company,
                        location: locationEl ? locationEl.textContent.trim() : 'N/A',
                    };
                });
            }"""
        )
        return [
            Job(
                title=j["title"],
                company=j["company"],
                location=j["location"],
                source=self.name,
                url=j["url"],
            )
            for j in raw_jobs
            if j.get("title") != "N/A"
        ]
