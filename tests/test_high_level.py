from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from cinema.exceptions import AmbiguousMatch, SeatUnavailable
from cinema.models import (
    CinemaLocation,
    Film,
    Seat,
    Showtime,
    TicketType,
    parse_date,
    parse_time,
)
from cinema.search import resolve


def location(identifier, name, city=""):
    return CinemaLocation(raw={}, id=identifier, name=name, city=city)


def test_search_exact_partial_and_id():
    items = [
        location("one", "Central Cinema", "Example City"),
        location("two", "Riverside Cinema", "Other City"),
    ]
    assert resolve("one", items).id == "one"
    assert resolve("riverside", items).id == "two"
    assert resolve("other", items).id == "two"
    assert resolve("cinema", items, best=False)[0].match_score is not None


def test_ambiguous_search():
    with pytest.raises(AmbiguousMatch):
        resolve("alpha", [location("1", "Alpha East"), location("2", "Alpha West")])


def test_human_dates_and_times():
    assert parse_date("tomorrow") == (date.today() + timedelta(days=1)).isoformat()
    assert parse_time("8pm") == 1200
    assert parse_time("around 8") == 480


def test_contiguous_and_central_seats():
    seats = [
        Seat(
            raw={},
            id=str(i),
            label=f"A{i}",
            row="A",
            number=str(i),
            position=i,
            available=i != 3,
        )
        for i in range(1, 8)
    ]

    class Client:
        def _high_seats(self, showing, refresh=True):
            return seats

    showing = Showtime(
        raw={},
        id="s",
        advertised_start=datetime.fromisoformat("2026-01-01T20:00"),
        _client=Client(),
    )
    assert [[s.label for s in group] for group in showing.contiguous_seats(2)] == [
        ["A1", "A2"],
        ["A4", "A5"],
        ["A5", "A6"],
        ["A6", "A7"],
    ]
    assert [s.label for s in showing.best_seats(2)] == ["A4", "A5"]
    with pytest.raises(SeatUnavailable):
        showing.seat("A3")


def test_models_serialize_and_print():
    cinema = location("x", "Example Cinema")
    film = Film(raw={"source": True}, id="f", title="Example Film", cinema=cinema)
    ticket = TicketType(raw={}, id="adult", name="Adult", price=12.5)
    assert str(cinema) == "Example Cinema"
    assert film.to_dict()["raw"] == {"source": True}
    assert ticket.to_dict()["price"] == 12.5


def test_accessible_seats_are_opt_in():
    seats = [
        Seat(
            raw={},
            id="1",
            label="A1",
            row="A",
            position=1,
            available=True,
            type="Normal",
        ),
        Seat(
            raw={},
            id="2",
            label="A2",
            row="A",
            position=2,
            available=True,
            type="Wheelchair",
        ),
        Seat(
            raw={},
            id="3",
            label="A3",
            row="A",
            position=3,
            available=True,
            type="Companion",
        ),
    ]

    class Client:
        def _high_seats(self, showing, refresh=True):
            return seats

    showing = Showtime(raw={}, id="s", _client=Client())
    assert [seat.label for seat in showing.available_seats()] == ["A1"]
    assert [seat.label for seat in showing.available_seats(accessible=True)] == [
        "A1",
        "A2",
        "A3",
    ]


def test_ticket_money_uses_decimal():
    ticket = TicketType(raw={}, id="a", name="Adult", price=Decimal("12.50"))
    assert ticket.price + Decimal("0.50") == Decimal("13.00")
