"""Analisis de frecuencia de palabras en ofertas de empleo."""

from collections import Counter

from src.analysis.stop_words import get_words_from_text


def count_words(jobs: list[dict], top_n: int = 50) -> list[tuple[str, int]]:
    """Cuenta frecuencia de palabras en titulos y descripciones de ofertas.

    Args:
        jobs: Lista de diccionarios Job (con campos title, description, etc.)
        top_n: Numero de palabras mas frecuentes a retornar.

    Returns:
        Lista de tuplas (palabra, frecuencia) ordenada de mayor a menor.
    """
    counter: Counter = Counter()

    for job in jobs:
        title = job.get("title") or ""
        description = job.get("description") or ""

        text = f"{title} {description}".strip()
        if not text:
            continue

        words = get_words_from_text(text)
        counter.update(words)

    return counter.most_common(top_n)
