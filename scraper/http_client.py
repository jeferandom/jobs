"""Cliente HTTP con retry y delay anti-ban."""

import time
import random
import requests
from config import HEADERS, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, MAX_RETRIES, RETRY_DELAY


def fetch_page(url: str) -> requests.Response | None:
    """Realiza GET con reintentos y delay aleatorio."""
    # TODO: Implementar logica de retry + delay
    pass


def get_page_url(base_url: str, path: str, page: int) -> str:
    """Construye URL para una pagina especifica."""
    # TODO: Construir URL con parametro ?p=N
    pass
