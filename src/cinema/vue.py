from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import requests

from ._http import decode_response
from .exceptions import CinemaAPIError, CinemaError

API_ROOT = "https://www.myvue.com/api/microservice"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


class VueClient:
    """Client for the public anonymous API used by the Vue UK website."""

    def __init__(self, *, timeout: float = 30, session: requests.Session | None = None, auto_connect: bool = True):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"Accept": "application/json", "Accept-Language": "en-GB,en;q=0.9", "Referer": "https://www.myvue.com/", "User-Agent": USER_AGENT})
        if auto_connect:
            self.connect()

    def __enter__(self):
        return self

    def __exit__(self, *_: object):
        self.close()

    def close(self):
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
        response = self.session.request(method, f"{API_ROOT}/{path.lstrip('/')}", params=params, json=json_body, timeout=self.timeout)
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

    def cinemas(self):
        return self.request("GET", "showings/cinemas")

    def films(self, cinema_id: str):
        return self.request("GET", "showings/films", params={"cinemaId": cinema_id})

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

