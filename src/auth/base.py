"""Interfaz base para proveedores de autenticación."""

from abc import ABC, abstractmethod
from enum import Enum
import threading


class LoginStatus(Enum):
    """Estados posibles de un proceso de login."""

    IDLE = "idle"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    ERROR = "error"


class AuthProvider(ABC):
    """Interfaz que deben implementar los proveedores de autenticación."""

    def __init__(self) -> None:
        self._status = LoginStatus.IDLE
        self._status_lock = threading.Lock()
        self._error_message: str | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Identificador del proveedor (ej: 'computrabajo')."""
        ...

    @property
    @abstractmethod
    def login_url(self) -> str:
        """URL donde se inicia el flujo de login."""
        ...

    @property
    @abstractmethod
    def success_url_contains(self) -> str:
        """Subcadena de URL que indica login exitoso."""
        ...

    @property
    def timeout_seconds(self) -> int:
        """Tiempo máximo de espera para el login manual."""
        return 120

    def get_status(self) -> LoginStatus:
        """Retorna el estado actual del login (thread-safe)."""
        with self._status_lock:
            return self._status

    def get_error_message(self) -> str | None:
        """Retorna el mensaje de error si status es ERROR."""
        with self._status_lock:
            return self._error_message

    def _set_status(self, status: LoginStatus, error: str | None = None) -> None:
        """Actualiza el estado de forma thread-safe."""
        with self._status_lock:
            self._status = status
            self._error_message = error

    @abstractmethod
    def start_login(self) -> bool:
        """Inicia el proceso de login en un hilo daemon.

        Returns:
            True si el login se inició, False si ya había uno en progreso.
        """
        ...

    @abstractmethod
    def cancel(self) -> None:
        """Solicita cancelar el login en progreso."""
        ...
