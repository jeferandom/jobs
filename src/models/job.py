"""Modelo de datos para ofertas de empleo."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Job:
    """Representa una oferta de empleo unificada."""

    title: str
    company: str
    location: str
    source: str
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())
    salary: str | None = None
    job_type: str | None = None  # presencial, remoto, hibrido
    url: str | None = None
    description: str | None = None
    is_urgent: bool = False
    is_featured: bool = False
