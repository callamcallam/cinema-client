from __future__ import annotations

from typing import Any

from .exceptions import CinemaAPIError


def decode_response(response: Any, method: str, path: str) -> Any:
    if response.status_code == 204 or not response.content:
        payload = None
    else:
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
    if not response.ok:
        raise CinemaAPIError(method.upper(), path, response.status_code, payload)
    return payload

