"""Interfaz base para adaptadores de fuentes de empleo."""

from abc import ABC, abstractmethod

from src.models.job import Job


class JobSource(ABC):
    """Interfaz comun que deben implementar todos los adaptadores de fuentes."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre de la fuente (ej: 'computrabajo', 'infojobs')."""
        ...

    @abstractmethod
    def search(self, keyword: str) -> list[Job]:
        """Busca ofertas por palabra clave y retorna lista de Job."""
        ...
