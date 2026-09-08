from __future__ import annotations

from typing import Any


class CinemaError(RuntimeError):
    """Base package exception."""


class ProviderError(CinemaError):
    pass


class AuthenticationError(ProviderError):
    pass


class CinemaNotFound(CinemaError):
    pass


class FilmNotFound(CinemaError):
    pass


class ShowtimeNotFound(CinemaError):
    pass


class SeatNotFound(CinemaError):
    pass


class SeatUnavailable(CinemaError):
    pass


class TicketTypeNotFound(CinemaError):
    pass


class BookingError(CinemaError):
    pass


class OrderCancellationError(BookingError):
    pass


class AmbiguousMatch(CinemaError):
    def __init__(self, query: str, matches: list[Any]):
        self.query, self.matches = query, matches
        super().__init__(
            f"{query!r} is ambiguous: " + ", ".join(str(x) for x in matches)
        )


class CinemaAPIError(ProviderError):
    def __init__(self, method: str, path: str, status_code: int, payload: Any):
        self.method, self.path, self.status_code, self.payload = (
            method,
            path,
            status_code,
            payload,
        )
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
