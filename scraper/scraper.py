"""Orquestador principal del scraper."""

import logging
from http_client import fetch_page, get_page_url
from parser import parse_job_listings, get_total_pages
from storage import save_to_csv, save_to_json
from config import BASE_URL, SEARCH_PATH

logger = logging.getLogger(__name__)


def scrape_all():
    """Recorre todas las paginas y guarda los resultados."""
    # TODO: Implementar logica principal
    pass


def scrape_page(page_num: int) -> list[dict]:
    """Scrapea una sola pagina y retorna la lista de ofertas."""
    # TODO: Fetch + parse de una pagina
    pass
