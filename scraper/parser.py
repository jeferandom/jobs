"""Parser de HTML con BeautifulSoup."""

from bs4 import BeautifulSoup


def parse_job_listings(html: str) -> list[dict]:
    """Extrae todas las ofertas de la pagina."""
    # TODO: Implementar parsing con selectores CSS identificados
    pass


def parse_job_card(article) -> dict:
    """Extrae datos de un article.box_offer individual."""
    # TODO: Extraer titulo, empresa, ubicacion, salario, etc.
    pass


def get_total_pages(html: str) -> int:
    """Obtiene el total de paginas desde el HTML."""
    # TODO: Leer h1.title_page > span.fwB para total de ofertas, dividir por 20
    pass
