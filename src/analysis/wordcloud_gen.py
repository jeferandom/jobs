"""Generador de nube de palabras para ofertas de empleo."""

from pathlib import Path

from src.analysis.word_frequency import count_words

try:
    from wordcloud import WordCloud
    WORDCLOUD_AVAILABLE = True
except ImportError:
    WORDCLOUD_AVAILABLE = False


def generate_wordcloud(
    jobs: list[dict],
    output_path: str = "data/wordcloud.png",
    width: int = 1200,
    height: int = 600,
    max_words: int = 100,
    background_color: str = "white",
) -> str | None:
    """Genera una imagen de nube de palabras a partir de ofertas.

    Args:
        jobs: Lista de diccionarios Job.
        output_path: Ruta donde guardar la imagen.
        width: Ancho de la imagen.
        height: Alto de la imagen.
        max_words: Maximo de palabras a mostrar.
        background_color: Color de fondo.

    Returns:
        Ruta del archivo generado o None si no hay datos.

    Raises:
        ImportError: Si la libreria wordcloud no esta instalada.
    """
    if not WORDCLOUD_AVAILABLE:
        raise ImportError(
            "La libreria 'wordcloud' no esta instalada. "
            "Ejecute: pip install wordcloud matplotlib"
        )

    word_freq = count_words(jobs, top_n=max_words)

    if not word_freq:
        return None

    freq_dict = dict(word_freq)

    wc = WordCloud(
        width=width,
        height=height,
        background_color=background_color,
        max_words=max_words,
        colormap="viridis",
        prefer_horizontal=0.7,
        min_font_size=10,
        max_font_size=120,
    )
    wc.generate_from_frequencies(freq_dict)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    wc.to_file(output_path)

    return output_path
