from __future__ import annotations

from typing import Any


class CinemaError(RuntimeError):
    """Base package exception."""


class CinemaAPIError(CinemaError):
    """A provider returned an unsuccessful response."""

    def __init__(self, method: str, path: str, status_code: int, payload: Any):
        self.method = method
        self.path = path
        self.status_code = status_code
        self.payload = payload
        detail = ""
        if isinstance(payload, dict):
            detail = str(
                payload.get("detail")
                or payload.get("title")
                or payload.get("errorMessage")
                or ""
            )
        message = f"{method} {path} failed with HTTP {status_code}"
        super().__init__(f"{message}: {detail}" if detail else message)

