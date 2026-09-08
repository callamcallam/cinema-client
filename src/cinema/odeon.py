from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

import requests

from ._http import decode_response
from .exceptions import CinemaError

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


class OdeonClient:
    """Client for the public API used by the ODEON UK website."""

    def __init__(
        self,
        site_id: str | None = None,
        *,
        timeout: float = 30,
        session: requests.Session | None = None,
        auto_connect: bool = True,
    ):
        self.site_id, self.timeout = site_id, timeout
        self.session = session or requests.Session()
        self.api_root: str | None = None
        if auto_connect:
            self.connect()

    def __enter__(self):
        return self

    def __exit__(self, *_: object):
        self.close()

    def close(self):
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
        response = self.session.request(
            method,
            f"{self.api_root}/{path.lstrip('/')}",
            params=params,
            json=json_body,
            timeout=self.timeout,
        )
        return decode_response(response, method, path)

    def _site(self, site_id: str | None = None) -> str:
        value = site_id or self.site_id
        if not value:
            raise ValueError("site_id is required")
        return value

    def cinemas(self):
        return self.request("GET", "sites")

    sites = cinemas

    def films(self, site_id: str | None = None):
        return self.request("GET", f"sites/{self._site(site_id)}/films")

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

