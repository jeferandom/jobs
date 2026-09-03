"""Interfaz base para adaptadores de fuentes de empleo."""

from abc import ABC, abstractmethod

from src.models.job import Job


class SessionExpiredError(Exception):
    """La sesión guardada expiró o es inválida; se requiere re-login."""


class JobSource(ABC):
    """Interfaz comun que deben implementar todos los adaptadores de fuentes."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre de la fuente (ej: 'computrabajo', 'infojobs')."""
        ...

    @property
    def requires_auth(self) -> bool:
        """True si la fuente requiere autenticación para este adaptador."""
        return False

    @abstractmethod
    def search(self, keyword: str, limit: int = 100) -> list[Job]:
        """Busca ofertas por palabra clave y retorna lista de Job."""
        ...

    def get_applied_jobs(self) -> list[Job]:
        """Obtiene las ofertas a las que el usuario está postulado.

        Solo aplica a fuentes con autenticación. Las fuentes públicas
        retornan lista vacía por defecto.

        Raises:
            SessionExpiredError: Si la sesión guardada ya no es válida.
        """
        return []
