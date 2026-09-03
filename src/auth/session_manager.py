"""Gestión de sesiones autenticadas (storage_state de Playwright)."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SESSION_DIR = Path("data/sessions")


class SessionManager:
    """Guarda, carga y elimina sesiones de autenticación por proveedor."""

    def _session_path(self, provider: str) -> Path:
        return SESSION_DIR / f"{provider}.json"

    def exists(self, provider: str) -> bool:
        """Retorna True si hay una sesión guardada para el proveedor."""
        return self._session_path(provider).exists()

    def save(self, provider: str, storage_state: dict) -> None:
        """Persiste el storage_state (cookies + localStorage) en disco."""
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        path = self._session_path(provider)
        path.write_text(json.dumps(storage_state, indent=2), encoding="utf-8")
        logger.info(f"Sesión guardada para {provider} en {path}")

    def load(self, provider: str) -> dict | None:
        """Carga el storage_state de un proveedor. None si no existe."""
        path = self._session_path(provider)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Sesión corrupta para {provider}: {e}")
            return None

    def delete(self, provider: str) -> bool:
        """Elimina la sesión guardada. Retorna True si existía."""
        path = self._session_path(provider)
        if path.exists():
            path.unlink()
            logger.info(f"Sesión eliminada para {provider}")
            return True
        return False
