from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from typing import Any

import requests

from ._http import decode_response
from .base import BaseClient, Capabilities, dictionaries
from .exceptions import CinemaAPIError, CinemaError
from .models import Booking, CinemaLocation, Film, Seat, Showtime, TicketType

API_ROOT = "https://www.myvue.com/api/microservice"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


class VueClient(BaseClient):
    """Client for the public anonymous API used by the Vue UK website."""

    provider = "vue"
    display_name = "Vue"
    website = "https://www.myvue.com/"
    capabilities = Capabilities()

    def __init__(self, *, timeout: float = 30, session: requests.Session | None = None, auto_connect: bool = True):
        self.timeout = timeout
        self._owns_session = session is None
        self.session = session or requests.Session()
        self._init_shared()
        self.session.headers.update({"Accept": "application/json", "Accept-Language": "en-GB,en;q=0.9", "Referer": "https://www.myvue.com/", "User-Agent": USER_AGENT})
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
        self._auth("/auth/token")
        return self

    def _auth(self, path: str):
        response = self.session.post(f"{API_ROOT}{path}", timeout=self.timeout)
        payload = decode_response(response, "POST", path)
        if isinstance(payload, dict) and payload.get("responseCode") not in (None, 0, "0"):
            raise CinemaAPIError("POST", path, response.status_code, payload)
        return payload

    def request(self, method: str, path: str, *, params=None, json_body=None, retry=True):
        for attempt in range(3):
            response = self.session.request(method, f"{API_ROOT}/{path.lstrip('/')}", params=params, json=json_body, timeout=self.timeout)
            if method.upper() != "GET" or response.status_code not in {429, 502, 503, 504} or attempt == 2: break
            time.sleep(0.25 * 2**attempt)
        if response.status_code == 401 and retry:
            try:
                self._auth("/auth/token/refresh")
            except Exception:
                self._auth("/auth/token")
            return self.request(method, path, params=params, json_body=json_body, retry=False)
        payload = decode_response(response, method, path)
        if isinstance(payload, dict):
            if payload.get("responseCode") not in (None, 0, "0") or payload.get("errorMessage"):
                raise CinemaAPIError(method, path, response.status_code, payload)
        return payload

    def cinemas(self, *, refresh: bool = False):
        return self._cached(("raw-cinemas",), lambda: self.request("GET", "showings/cinemas"), refresh)

    def films(self, cinema_id: str, *, refresh: bool = False):
        return self._cached(("raw-films", cinema_id), lambda: self.request("GET", "showings/films", params={"cinemaId": cinema_id}), refresh)

    def dates(self, cinema_id: str, film_id: str):
        return self.request("GET", "showings/showingDates", params={"cinemaId": cinema_id, "filmId": film_id, "minEmbargoLevel": 1, "forNextWeek": "true"})

    def showtimes(self, cinema_id: str, film_id: str, date: str):
        return self.request("GET", f"showings/cinemas/{cinema_id}/films/{film_id}/showingGroups", params={"showingDate": date})

    def showing(self, cinema_id: str, session_id: str):
        return self.request("GET", f"showings/cinemas/{cinema_id}/showings/{session_id}")

    def tickets(self, cinema_id: str, session_id: str):
        return self.request("GET", f"booking/Session/{cinema_id}/{session_id}/tickets")

    def seats(self, cinema_id: str, session_id: str, order_id: str | None = None):
        params = {"orderSessionId": order_id} if order_id else None
        return self.request("GET", f"booking/Session/{cinema_id}/{session_id}/seats", params=params)

    @staticmethod
    def make_order(cinema_id: str, session_id: str, email: str, ticket: Mapping[str, Any], seats: Sequence[Mapping[str, int]]):
        """Build an order body from a ticket and seat coordinates."""
        return {
            "cinemaId": cinema_id,
            "sessionId": session_id,
            "customer": {"email": email},
            "tickets": [{
                "areaCategoryCode": ticket["areaCategoryCode"],
                "code": ticket["code"],
                "priceInCents": ticket["priceInCents"],
                "seats": [dict(seat) for seat in seats],
            }],
        }

    def create_order(self, order: Mapping[str, Any]):
        return self.request("POST", "booking/order", json_body=dict(order))

    def update_order(self, order_id: str, order: Mapping[str, Any]):
        return self.request("PUT", f"booking/order/{order_id}", json_body=dict(order))

    def get_order(self, order_id: str):
        return self.request("GET", f"booking/order/{order_id}")

    def cancel_order(self, order_id: str) -> None:
        self.request("DELETE", f"booking/order/{order_id}")

    delete_order = cancel_order

    def locations(self, *, refresh=False):
        def load():
            result = []
            for item in dictionaries(self.cinemas(refresh=refresh), ("result", "cinemas", "items")):
                identifier = str(item.get("cinemaId") or item.get("id") or ""); name = str(item.get("cinemaName") or item.get("name") or "")
                if identifier and name: result.append(CinemaLocation(raw=item, id=identifier, name=name, city=str(item.get("city") or item.get("town") or ""), address=str(item.get("address") or ""), _client=self))
            return result
        return self._cached(("locations",), load, refresh)

    def _high_films(self, cinema, *, refresh=False):
        result = []
        for item in dictionaries(self.films(cinema.id, refresh=refresh), ("result", "films", "items")):
            identifier = str(item.get("filmId") or item.get("id") or ""); title = str(item.get("filmTitle") or item.get("title") or item.get("name") or "")
            if identifier and title and item.get("hasSessions", True): result.append(Film(raw=item, id=identifier, title=title, runtime=item.get("runningTime"), rating=str((item.get("certificate") or {}).get("name") or ""), cinema=cinema, _client=self))
        return result

    def _high_dates(self, film, *, refresh=False):
        payload = self._cached(("dates", film.cinema.id, film.id), lambda: self.dates(film.cinema.id, film.id), refresh)
        values = payload.get("result") or payload.get("dates") or []
        return [str(x.get("date") or x.get("showingDate") if isinstance(x, dict) else x) for x in values]

    def _high_showtimes(self, film, date, *, refresh=False):
        payload = self._cached(("showtimes", film.cinema.id, film.id, date), lambda: self.showtimes(film.cinema.id, film.id, date), refresh); result = []
        for group in payload.get("result", []):
            for item in group.get("sessions", []):
                identifier = str(item.get("sessionId") or ""); start = str(item.get("startTime") or item.get("showingTime") or item.get("start") or "")
                attrs = [str(x.get("shortName") or x.get("name") or "") for x in item.get("attributes", [])]
                if identifier: result.append(Showtime(raw=item, id=identifier, datetime=start, screen=str(item.get("screen") or ""), experience=", ".join(filter(None, attrs)), cinema=film.cinema, film=film, _client=self))
        return sorted(result, key=lambda x: x.datetime)

    def _high_seats(self, showing, *, refresh=True):
        payload = self.seats(showing.cinema.id, showing.id); result = []
        for row in (payload.get("result") or {}).get("seatRows", []):
            for item in row.get("columns", []):
                label = str(item.get("name") or ""); match_row = ''.join(c for c in label if c.isalpha()); number = ''.join(c for c in label if c.isdigit())
                if label: result.append(Seat(raw=item, id=label, label=label, row=match_row, number=number, position=int(item.get("columnIndex") or 0), available=int(item.get("seatStatus") or 0) == 0, type=str(item.get("seatType") or "standard")))
        return result

    def _high_tickets(self, showing):
        payload = self.tickets(showing.cinema.id, showing.id); result = []
        for item in dictionaries(payload, ("result", "tickets", "items")):
            identifier = str(item.get("code") or item.get("ticketTypeId") or item.get("id") or ""); name = str(item.get("name") or item.get("description") or identifier); cents = item.get("priceInCents") or item.get("price")
            if identifier: result.append(TicketType(raw=item, id=identifier, name=name, price=float(cents)/100 if cents is not None else None))
        return result

    def _high_book(self, showing, seats, ticket, *, email=None):
        if not email: raise ValueError("email is required for Vue bookings")
        selected = showing.seats(seats); ticket_type = showing.ticket(ticket)
        coordinates = [{"areaNumber": s.raw["areaNumber"], "rowIndex": s.raw["rowIndex"], "columnIndex": s.raw["columnIndex"]} for s in selected]
        ticket_data = {"areaCategoryCode": ticket_type.raw.get("areaCategoryCode") or selected[0].raw.get("areaCategoryCode"), "code": ticket_type.id, "priceInCents": ticket_type.raw.get("priceInCents") or int((ticket_type.price or 0)*100)}
        body = self.make_order(showing.cinema.id, showing.id, email, ticket_data, coordinates); created = self.create_order(body); order_id = str((created.get("result") or created).get("orderSessionId") or "")
        if not order_id: raise CinemaError("Vue did not return an orderSessionId")
        return Booking(raw=created, order_id=order_id, cinema=showing.cinema, film=showing.film, showtime=showing, seats=selected, tickets=[ticket_type]*len(selected), _client=self)
