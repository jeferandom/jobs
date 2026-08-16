"""Adaptador de Computrabajo para el scraper de empleos."""

import logging
import random
import time

import requests
from bs4 import BeautifulSoup, Tag

from src.models.job import Job
from src.scrapers.base import JobSource

logger = logging.getLogger(__name__)

BASE_URL = "https://co.computrabajo.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}

ITEMS_PER_PAGE = 20
REQUEST_DELAY = (2, 4)
MAX_RETRIES = 3


class ComputrabajoScraper(JobSource):
    """Scraper de la fuente Computrabajo."""

    @property
    def name(self) -> str:
        return "computrabajo"

    def search(self, keyword: str) -> list[Job]:
        """Busca ofertas en Computrabajo por palabra clave."""
        keyword = keyword.strip().lower().replace(" ", "-")
        search_path = f"/trabajo-de-{keyword}"

        jobs: list[Job] = []
        page = 1

        while True:
            logger.info(f"Página {page} - {BASE_URL}{search_path}?p={page}")
            html = self._fetch_page(f"{BASE_URL}{search_path}?p={page}")

            if html is None:
                logger.warning(f"No se pudo obtener la página {page}")
                break

            if page == 1:
                total = self._get_total_results(html)
                total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
                logger.info(f"Total de ofertas: {total} ({total_pages} páginas)")

            page_jobs = self._parse_job_listings(html)
            if not page_jobs:
                logger.info("No se encontraron más ofertas")
                break

            jobs.extend(page_jobs)
            page += 1
            time.sleep(random.uniform(*REQUEST_DELAY))

        logger.info(f"Total scrapeado: {len(jobs)} ofertas")
        return jobs

    def _fetch_page(self, url: str) -> str | None:
        """Realiza GET con reintentos."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(url, headers=HEADERS, timeout=10)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                logger.warning(f"Intento {attempt}/{MAX_RETRIES} falló: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(5)
        return None

    def _get_total_results(self, html: str) -> int:
        """Obtiene el total de ofertas desde el HTML."""
        soup = BeautifulSoup(html, "lxml")
        span = soup.select_one("h1.title_page span.fwB")
        if span:
            return int(span.text.strip().replace(".", "").replace(",", ""))
        return 0

    def _parse_job_listings(self, html: str) -> list[Job]:
        """Extrae todas las ofertas de una página."""
        soup = BeautifulSoup(html, "lxml")
        articles = soup.select("article.box_offer[data-id]")
        return [self._parse_job_card(a) for a in articles]

    def _parse_job_card(self, article: Tag) -> Job:
        """Extrae datos de un article.box_offer individual."""
        title_tag = article.select_one("h2 a.js-o-link")
        title = title_tag.text.strip() if title_tag else "N/A"

        href = title_tag["href"] if title_tag and title_tag.has_attr("href") else None
        url = f"{BASE_URL}{href}" if href else None

        company_tag = article.select_one("a[offer-grid-article-company-url]")
        if company_tag:
            company = company_tag.text.strip()
        else:
            p_dflex = article.select_one("p.dFlex.vm_fx.fs16.fc_base.mt5")
            company = p_dflex.text.strip() if p_dflex else "N/A"

        location_tag = article.select_one("p.fs16.fc_base.mt5 span.mr10")
        location = location_tag.text.strip() if location_tag else "N/A"

        salary = None
        salary_parent = article.select_one("div.fs13.mt15")
        if salary_parent:
            salary_icon = salary_parent.select_one("span.icon.i_salary")
            if salary_icon and salary_icon.parent:
                salary = salary_parent.text.strip().split("\n")[0].strip()

        job_type = None
        if salary_parent:
            if salary_parent.select_one("span.icon.i_home_office"):
                job_type = "hibrido"
            elif salary_parent.select_one("span.icon.i_home"):
                job_type = "remoto"
            else:
                job_type = "presencial"

        is_urgent = article.select_one("span.fc_urgent") is not None
        is_featured = "outstanding" in article.get("class", [])

        return Job(
            title=title,
            company=company,
            location=location,
            source=self.name,
            url=url,
            salary=salary,
            job_type=job_type,
            is_urgent=is_urgent,
            is_featured=is_featured,
        )
