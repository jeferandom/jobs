"""Entry point del sistema de scraping de empleos."""

import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scrapers.computrabajo import ComputrabajoScraper
from src.scrapers.base import JobSource
from src.models.job import Job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def save_to_csv(jobs: list[Job], filename: str = "jobs.csv") -> None:
    """Guarda una lista de Job en un archivo CSV."""
    if not jobs:
        logger.warning("No hay ofertas para guardar")
        return

    fieldnames = list(jobs[0].__dataclass_fields__.keys())
    with open(f"data/{filename}", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            writer.writerow(job.__dict__)

    logger.info(f"Guardadas {len(jobs)} ofertas en data/{filename}")


def get_scrapers() -> list[JobSource]:
    """Retorna la lista de adaptadores disponibles."""
    return [
        ComputrabajoScraper(),
    ]


if __name__ == "__main__":
    keyword = input("Palabra clave de búsqueda: ").strip()
    if not keyword:
        keyword = "desarrollador"

    all_jobs: list[Job] = []

    for scraper in get_scrapers():
        logger.info(f"Scrapeando {scraper.name}...")
        jobs = scraper.search(keyword)
        all_jobs.extend(jobs)

    save_to_csv(all_jobs, f"jobs_{keyword.replace(' ', '_')}.csv")
