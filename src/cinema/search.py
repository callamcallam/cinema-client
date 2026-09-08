from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Protocol

from .exceptions import AmbiguousMatch


class Searchable(Protocol):
    id: str
    match_score: float | None

    def search_text(self) -> str: ...


ALIASES = {"lon": "london", "ldn": "london", "leics": "leicester"}


def normalize(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return ALIASES.get(value, value)


def score(query: str, item: Searchable) -> float:
    q, identifier, text = (
        normalize(query),
        normalize(item.id),
        normalize(item.search_text()),
    )
    if q == identifier or q == text:
        return 100.0
    if q and q in text:
        return min(99.0, 85 + 14 * len(q) / max(len(text), 1))
    return max(
        [
            SequenceMatcher(None, q, text).ratio() * 100,
            *[SequenceMatcher(None, q, word).ratio() * 100 for word in text.split()],
        ]
    )


def resolve(
    query: str,
    items: list[Searchable],
    *,
    best: bool = True,
    limit: int = 5,
    strict: bool = False,
):
    ranked = sorted(
        ((score(query, item), item) for item in items),
        key=lambda pair: pair[0],
        reverse=True,
    )
    ranked = [(s, item) for s, item in ranked if s >= (90 if strict else 55)][:limit]
    for s, item in ranked:
        item.match_score = round(s, 1)
    matches = [item for _, item in ranked]
    if not best:
        return matches
    if not matches:
        return None
    if len(ranked) > 1 and ranked[0][0] < 100 and ranked[0][0] - ranked[1][0] < 4:
        raise AmbiguousMatch(query, matches)
    return matches[0]
