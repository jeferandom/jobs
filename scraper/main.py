"""Entry point del scraper."""

import logging
from scraper import scrape_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

if __name__ == "__main__":
    scrape_all()
