from __future__ import annotations

import json
import time
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

import requests

from ._http import decode_response
from .base import BaseClient, Capabilities, dictionaries, text
from .exceptions import CinemaError
from .models import Booking, CinemaLocation, Film, Seat, Showtime, TicketType

HOME = "https://www.odeon.co.uk/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


def _initial_data(text: str) -> dict[str, Any]:
    marker = text.find("window.initialData")
    start = text.find("{", marker)
    if marker < 0 or start < 0:
        raise CinemaError("ODEON bootstrap data was not found")
    depth, quoted, escaped = 0, False, False
    for end in range(start, len(text)):
        char = text[end]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : end + 1])
    raise CinemaError("ODEON bootstrap data was incomplete")


class OdeonClient(BaseClient):
    """Client for the public API used by the ODEON UK website."""

    provider = "odeon"
    display_name = "ODEON"
    website = HOME
    capabilities = Capabilities(seat_layout=True)

    def __init__(
        self,
        site_id: str | None = None,
        *,
        timeout: float = 30,
        session: requests.Session | None = None,
        auto_connect: bool = True,
    ):
        self.site_id, self.timeout = site_id, timeout
        self._owns_session = session is None
        self.session = session or requests.Session()
        self.api_root: str | None = None
        self._init_shared()
        if auto_connect:
            self.connect()

    def __enter__(self):
        return self

    def __exit__(self, *_: object):
        self.close()

    def close(self):
        if self._owns_session:
            self.session.close()

    def connect(self):
        response = self.session.get(
            HOME,
            timeout=self.timeout,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-GB,en;q=0.9"},
        )
        response.raise_for_status()
        api = _initial_data(response.text).get("api", {})
        api_url, token, region = api.get("apiUrl"), api.get("authToken"), api.get("regionCode")
        if not all(isinstance(x, str) and x for x in (api_url, token, region)):
            raise CinemaError("ODEON bootstrap settings were incomplete")
        self.api_root = f"{api_url.rstrip('/')}/ocapi/v1"
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "connect-region-code": region,
                "Origin": HOME.rstrip("/"),
                "Referer": HOME,
                "User-Agent": USER_AGENT,
            }
        )
        return self

    def request(self, method: str, path: str, *, params=None, json_body=None):
        if not self.api_root:
            raise CinemaError("ODEON client is not connected")
        for attempt in range(3):
            response = self.session.request(method, f"{self.api_root}/{path.lstrip('/')}", params=params, json=json_body, timeout=self.timeout)
            if method.upper() != "GET" or response.status_code not in {429, 502, 503, 504} or attempt == 2: break
            time.sleep(0.25 * 2**attempt)
        return decode_response(response, method, path)

    def _site(self, site_id: str | None = None) -> str:
        value = site_id or self.site_id
        if not value:
            raise ValueError("site_id is required")
        return value

    def cinemas(self, *, refresh: bool = False):
        return self._cached(("raw-cinemas",), lambda: self.request("GET", "sites"), refresh)

    sites = cinemas

    def films(self, site_id: str | None = None, *, refresh: bool = False):
        selected = self._site(site_id)
        return self._cached(("raw-films", selected), lambda: self.request("GET", f"sites/{selected}/films"), refresh)

    def dates(self, film_id: str, site_id: str | None = None):
        return self.request("GET", "film-screening-dates", params=(("filmIds", film_id), ("siteIds", self._site(site_id))))

    def showtimes(self, film_id: str, date: str, site_id: str | None = None):
        return self.request("GET", f"showtimes/by-business-date/{date}", params=(("filmIds", film_id), ("siteIds", self._site(site_id))))

    def seat_layout(self, layout_id: str):
        return self.request("GET", f"seat-layouts/{layout_id}")

    def seats(self, showtime_id: str):
        return self.request("GET", f"showtimes/{showtime_id}/seat-availability")

    def tickets(self, showtime_id: str):
        return self.request("GET", f"showtimes/{showtime_id}/ticket-prices")

    def create_order(self, site_id: str | None = None):
        return self.request("POST", "orders/standard/booking", json_body={"siteId": self._site(site_id), "bookingMode": "Paid"})

    def set_showtime(self, order_id: str, showtime_id: str, seats: Sequence[str], tickets: Sequence[Mapping[str, str]] = ()):
        return self.request("PUT", f"orders/{order_id}/showtimes/{showtime_id}", json_body={"seats": list(seats), "tickets": list(tickets)})

    @staticmethod
    def make_tickets(ticket_type_id: str, quantity: int):
        return [{"id": str(uuid.uuid4()), "ticketTypeId": ticket_type_id} for _ in range(quantity)]

    def cancel_order(self, order_id: str) -> None:
        self.request("DELETE", f"orders/{order_id}")

    delete_order = cancel_order

    def locations(self, *, refresh=False):
        def load():
            result = []
            for item in dictionaries(self.cinemas(refresh=refresh), ("sites", "items", "value")):
                identifier, name = str(item.get("id") or item.get("siteId") or ""), text(item.get("name"))
                contact = item.get("contactDetails") or {}; address = contact.get("address") or {}
                if identifier and name: result.append(CinemaLocation(raw=item, id=identifier, name=name, city=str(address.get("city") or ""), address=str(address.get("line1") or address.get("addressLine1") or ""), _client=self))
            return result
        return self._cached(("locations",), load, refresh)

    def _high_films(self, cinema, *, refresh=False):
        def load():
            result = []
            for item in dictionaries(self.films(cinema.id, refresh=refresh), ("films", "items", "value")):
                identifier = str(item.get("id") or item.get("ID") or item.get("filmId") or item.get("ScheduledFilmId") or "")
                title = text(item.get("title")) or str(item.get("Title") or item.get("name") or "")
                if identifier and title: result.append(Film(raw=item, id=identifier, title=title, runtime=item.get("runtimeInMinutes"), rating=text(item.get("rating")), cinema=cinema, _client=self))
            return result
        return self._cached(("films", cinema.id), load, refresh)

    def _high_dates(self, film, *, refresh=False):
        payload = self._cached(("dates", film.cinema.id, film.id), lambda: self.dates(film.id, film.cinema.id), refresh)
        values = payload.get("businessDates") or payload.get("dates") or []
        return [str(x.get("businessDate") if isinstance(x, dict) else x) for x in values]

    def _high_showtimes(self, film, date, *, refresh=False):
        payload = self._cached(("showtimes", film.cinema.id, film.id, date), lambda: self.showtimes(film.id, date, film.cinema.id), refresh)
        result = []
        for item in dictionaries(payload, ("showtimes",)):
            identifier = str(item.get("id") or item.get("ID") or ""); schedule = item.get("schedule") or {}
            if identifier: result.append(Showtime(raw=item, id=identifier, datetime=str(schedule.get("startsAt") or item.get("startsAt") or item.get("Showtime") or ""), screen=str(item.get("screenId") or ""), layout_id=str(item.get("seatLayoutId") or ""), cinema=film.cinema, film=film, _client=self))
        return sorted(result, key=lambda x: x.datetime)

    def _high_seats(self, showing, *, refresh=True):
        layout = self.seat_layout(showing.layout_id); availability = self.seats(showing.id)
        statuses = {str(x.get("seatId")): str(x.get("status")) for x in availability.get("seatAvailabilities", [])}
        result = []
        for area in (layout.get("seatLayout") or {}).get("areas", []):
            for row in area.get("rows", []):
                for item in row.get("seats", []):
                    pos = item.get("position") or {}; identifier = str(item.get("id") or "")
                    label = f"{item.get('rowLabel') or row.get('label') or ''}{item.get('label') or ''}"
                    if identifier: result.append(Seat(raw=item, id=identifier, label=label, row=str(item.get("rowLabel") or row.get("label") or ""), number=str(item.get("label") or ""), position=int(pos.get("columnNumber") or 0), available=statuses.get(identifier) == "Available", type=str(item.get("type") or "standard")))
        return result

    def _high_tickets(self, showing):
        payload = self.tickets(showing.id); metadata = {str(x.get("id")): x for x in (payload.get("relatedData") or {}).get("ticketTypes", [])}
        result = []
        for item in payload.get("ticketPrices", []):
            identifier = str(item.get("ticketTypeId") or ""); meta = metadata.get(identifier, {}); price = (item.get("price") or {}).get("valueIncludingTax")
            if identifier: result.append(TicketType(raw=item, id=identifier, name=text(meta.get("description")) or text(meta.get("name")) or identifier, price=float(price) if price is not None else None))
        return result

    def _high_book(self, showing, seats, ticket, *, email=None):
        selected = showing.seats(seats); ticket_type = showing.ticket(ticket); created = self.create_order(showing.cinema.id); order = created.get("order", created); order_id = str(order["id"])
        try:
            ids = [seat.id for seat in selected]; self.set_showtime(order_id, showing.id, ids); self.set_showtime(order_id, showing.id, ids, self.make_tickets(ticket_type.id, len(ids)))
        except Exception:
            try: self.cancel_order(order_id)
            finally: raise
        return Booking(raw=created, order_id=order_id, cinema=showing.cinema, film=showing.film, showtime=showing, seats=selected, tickets=[ticket_type]*len(selected), _client=self)
