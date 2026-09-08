from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .exceptions import CinemaNotFound
from .search import resolve


@dataclass(frozen=True)
class Capabilities:
    cinemas: bool = True; films: bool = True; showtimes: bool = True; seats: bool = True; tickets: bool = True; orders: bool = True; seat_layout: bool = False

class BaseClient:
    provider = ""; display_name = ""; website = ""; capabilities = Capabilities()
    def _init_shared(self): self._cache: dict[tuple[Any, ...], Any] = {}
    def clear_cache(self): self._cache.clear()
    def _cached(self, key, loader: Callable[[], Any], refresh=False):
        if refresh or key not in self._cache: self._cache[key] = loader()
        return self._cache[key]
    def locations(self, *, refresh=False): raise NotImplementedError
    def search(self, query: str, *, best=True, limit=5, strict=False):
        result = resolve(query, self.locations(), best=best, limit=limit, strict=strict)
        if best and result is None: raise CinemaNotFound(f"No {self.display_name} cinema matched {query!r}")
        return result
    resolve_cinema = search

def dictionaries(value: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, list) and all(isinstance(x, dict) for x in candidate): return candidate
        for candidate in value.values():
            found = dictionaries(candidate, keys)
            if found: return found
    return []

def text(value: Any) -> str:
    if isinstance(value, str): return value
    if isinstance(value, dict): return str(value.get("text") or value.get("name") or "")
    return str(value or "")
