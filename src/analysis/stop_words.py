"""Stop words en español para analisis de ofertas de empleo."""

import unicodedata
import re

STOP_WORDS_BASE = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las",
    "por", "un", "para", "con", "no", "una", "su", "al", "lo", "como",
    "mas", "pero", "sus", "le", "ya", "o", "este", "si", "porque", "esta",
    "entre", "cuando", "muy", "sin", "sobre", "tambien", "me", "hasta",
    "hay", "donde", "quien", "desde", "todo", "nos", "durante", "todos",
    "uno", "les", "ni", "contra", "otros", "ese", "eso", "ante", "ellos",
    "e", "esto", "mi", "antes", "algunos", "que", "unos", "yo", "otro",
    "otras", "otra", "el", "l", "tan", "aunque", "sea", "mas", "fue",
    "ser", "es", "son", "era", "fui", "fuimos", "eran", "sido", "he",
    "has", "ha", "hemos", "han", "tengo", "tienes", "tiene", "tenemos",
    "tienen", "habia", "habian", "haber", "tiene", "tener", "hacer",
    "cada", "bien", "todo", "todos", "toda", "todas", "algo", "nada",
    "poco", "mucho", "demasiado", "bastante", "mismo", "misma",
    "aqui", "ahi", "alla", "asi", "donde", "como", "cuando",
    "que", "cual", "cuales", "quien", "quienes",
}

STOP_WORDS_LABORALES = {
    "empresa", "trabajo", "trabajar", "empleo", "empleos", "vacante",
    "funciones", "requisitos", "beneficios", "experiencia", "conocimientos",
    "equipo", "cliente", "clientes", "proyecto", "proyectos", "area",
    "sector", "perfil", "candidato", "candidatos", "contratacion",
    "disponibilidad", "horario", "jornada", "laboral", "laborales",
    "profesional", "profesionales", "capacitacion", "capacitaciones",
    "oportunidad", "oportunidades", "interes", "interesados",
    "enviar", "cv", "hoja", "vida", "correo", "email", "telefono",
    "CONTACTO", "INFORMACION", "ADICIONAL", "DATOS",
    "somos", "contamos", "ofrecemos", "brindamos", "buscamos",
    "requisimos", "solicitamos", "requerimos", "consideramos",
    "nivel", "alto", "medio", "basico", "avanzado",
    "anos", "años", "meses", "exigimos", "exigencia",
    "habilidades", "competencias", "aptitudes", "cualidades",
    "responsabilidades", "actividades", "tareas",
    "inmediato", "inmediata", "posible", "oportunidad",
    "crecimiento", "desarrollo", "formacion",
}

ALL_STOP_WORDS = STOP_WORDS_BASE | STOP_WORDS_LABORALES


def normalize_text(text: str) -> str:
    """Normaliza texto: minusculas, sin acentos, sin puntuacion."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def filter_stop_words(words: list[str], extra_excludes: set[str] | None = None) -> list[str]:
    """Filtra stop words de una lista de palabras."""
    excluded = ALL_STOP_WORDS.copy()
    if extra_excludes:
        excluded |= extra_excludes
    return [w for w in words if w not in excluded and len(w) > 2]


def get_words_from_text(text: str, extra_excludes: set[str] | None = None) -> list[str]:
    """Extrae palabras limpias de un texto."""
    normalized = normalize_text(text)
    words = normalized.split()
    return filter_stop_words(words, extra_excludes)
