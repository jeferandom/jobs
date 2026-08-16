"""Configuración del scraper de Computrabajo."""

BASE_URL = "https://co.computrabajo.com"
SEARCH_PATH = "/trabajo-de-desarrollador"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Delay entre requests (segundos)
REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 4

# Reintentos maximos
MAX_RETRIES = 3
RETRY_DELAY = 5

# Output
OUTPUT_CSV = "ofertas_computrabajo.csv"
OUTPUT_JSON = "ofertas_computrabajo.json"
