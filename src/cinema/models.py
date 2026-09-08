from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from .exceptions import (
    FilmNotFound,
    SeatNotFound,
    SeatUnavailable,
    ShowtimeNotFound,
    TicketTypeNotFound,
)
from .search import resolve

if TYPE_CHECKING:
    from .base import BaseClient

@dataclass
class Model:
    raw: dict[str, Any] = field(repr=False)
    match_score: float | None = None
    def to_dict(self): return {k: v for k, v in vars(self).items() if not k.startswith("_")}

@dataclass
class CinemaLocation(Model):
    id: str = ""; name: str = ""; address: str = ""; city: str = ""
    _client: BaseClient | None = field(default=None, repr=False)
    def __str__(self): return self.name
    def search_text(self): return f"{self.name} {self.city}"
    def films(self, *, refresh=False): return self._client._high_films(self, refresh=refresh)  # type: ignore[union-attr]
    def search_films(self, query, *, limit=5): return resolve(query, self.films(), best=False, limit=limit)
    def film(self, query):
        found = resolve(query, self.films())
        if found is None: raise FilmNotFound(f"No film matched {query!r} at {self.name}")
        return found

@dataclass
class Film(Model):
    id: str = ""; title: str = ""; rating: str = ""; runtime: int | None = None
    _client: BaseClient | None = field(default=None, repr=False); cinema: CinemaLocation | None = field(default=None, repr=False)
    def __str__(self): return self.title
    def search_text(self): return self.title
    def dates(self, *, refresh=False): return self._client._high_dates(self, refresh=refresh)  # type: ignore[union-attr]
    def showtimes(self, when=None, *, refresh=False):
        available = self.dates(refresh=refresh)
        chosen = parse_date(when or (available[0] if available else "today"))
        return self._client._high_showtimes(self, chosen, refresh=refresh)  # type: ignore[union-attr]
    def time(self, query, when=None):
        options, wanted = self.showtimes(when), parse_time(query)
        ranked = sorted((abs(minutes(x.datetime)-wanted), x) for x in options)
        if not ranked or ranked[0][0] > 90: raise ShowtimeNotFound(f"No sensible match for {query!r}; available: {', '.join(x.time for x in options)}")
        return ranked[0][1]

@dataclass
class Showtime(Model):
    id: str = ""; datetime: str = ""; screen: str = ""; experience: str = ""; layout_id: str = ""
    _client: BaseClient | None = field(default=None, repr=False); cinema: CinemaLocation | None = field(default=None, repr=False); film: Film | None = field(default=None, repr=False)
    @property
    def time(self):
        found = re.search(r"(\d{2}:\d{2})", self.datetime); return found.group(1) if found else self.datetime
    def __str__(self): return f"{self.film or 'Film'} - {self.time}" + (f" - Screen {self.screen}" if self.screen else "")
    def seats(self, *labels, refresh=True):
        all_seats = self._client._high_seats(self, refresh=refresh)  # type: ignore[union-attr]
        if not labels: return all_seats
        wanted = labels[0] if len(labels) == 1 and isinstance(labels[0], (list, tuple)) else labels
        result = []
        for label in wanted:
            seat = next((s for s in all_seats if s.label.lower() == str(label).lower()), None)
            if not seat: raise SeatNotFound(f"Seat {label} does not exist")
            if not seat.available: raise SeatUnavailable(f"Seat {label} is unavailable")
            result.append(seat)
        return result
    def seat(self, label): return self.seats(label)[0]
    def available_seats(self, *, row=None, seat_type=None, refresh=True): return [s for s in self.seats(refresh=refresh) if s.available and (not row or s.row.lower() == row.lower()) and (not seat_type or s.type.lower() == seat_type.lower())]
    def contiguous_seats(self, count, *, row=None):
        groups, rows = [], {}
        for seat in self.available_seats(row=row): rows.setdefault(seat.row, []).append(seat)
        for seats in rows.values():
            seats.sort(key=lambda s: s.position)
            for index in range(len(seats)-count+1):
                block = seats[index:index+count]
                if all(block[i+1].position == block[i].position+1 for i in range(len(block)-1)): groups.append(block)
        return groups
    def best_seats(self, count, *, together=True, row=None):
        available = self.available_seats(row=row)
        if not together: return available[:count]
        groups = self.contiguous_seats(count, row=row)
        if not groups: raise SeatUnavailable(f"No contiguous block of {count} seats is available")
        centre = (min(s.position for s in available)+max(s.position for s in available))/2
        return min(groups, key=lambda g: abs(sum(s.position for s in g)/len(g)-centre))
    def ticket_types(self): return self._client._high_tickets(self)  # type: ignore[union-attr]
    def ticket(self, query):
        found = resolve(query, self.ticket_types())
        if found is None: raise TicketTypeNotFound(f"No ticket matched {query!r}")
        return found
    def book(self, *, seats, ticket="adult", email=None): return self._client._high_book(self, seats, ticket, email=email)  # type: ignore[union-attr]

@dataclass
class Seat(Model):
    id: str = ""; label: str = ""; row: str = ""; number: str = ""; position: int = 0; available: bool = False; type: str = "standard"
    def __str__(self): return self.label
    def search_text(self): return self.label
@dataclass
class TicketType(Model):
    id: str = ""; name: str = ""; price: float | None = None
    def __str__(self): return self.name
    def search_text(self): return self.name
@dataclass
class Booking(Model):
    order_id: str = ""; cinema: CinemaLocation | None = None; film: Film | None = None; showtime: Showtime | None = None; seats: list[Seat] = field(default_factory=list); tickets: list[TicketType] = field(default_factory=list); _client: BaseClient | None = field(default=None, repr=False); cancelled: bool = False
    def cancel(self):
        if not self.cancelled: self._client.cancel_order(self.order_id); self.cancelled = True  # type: ignore[union-attr]

def parse_date(value):
    value = value.strip().lower(); today = date.today()
    if value == "today": return today.isoformat()
    if value == "tomorrow": return (today+timedelta(days=1)).isoformat()
    try: return date.fromisoformat(value).isoformat()
    except ValueError: pass
    days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    matches = [i for i, day in enumerate(days) if day.startswith(value)]
    if len(matches) == 1: return (today+timedelta(days=(matches[0]-today.weekday())%7 or 7)).isoformat()
    raise ValueError(f"Unsupported date {value!r}")
def parse_time(value):
    value = value.lower().replace("around", "").replace(" ", "")
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm)?", value)
    if not match: raise ValueError(f"Unsupported time {value!r}")
    hour, minute, suffix = int(match.group(1)), int(match.group(2) or 0), match.group(3)
    if suffix: hour = hour%12+(12 if suffix == "pm" else 0)
    return hour*60+minute
def minutes(value):
    match = re.search(r"(\d{2}):(\d{2})", value); return int(match.group(1))*60+int(match.group(2)) if match else 0
