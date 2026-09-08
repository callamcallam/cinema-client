import json
from pathlib import Path

from cinema import CinemaLocation, Film
from cinema.odeon import OdeonClient

FIXTURES = Path(__file__).parent / "fixtures" / "odeon"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def client_and_film():
    client = OdeonClient(auto_connect=False)
    cinema = CinemaLocation(raw={}, id="SITE_ID", name="Example", _client=client)
    return client, Film(
        raw={}, id="FILM_ID", title="Example Film", cinema=cinema, _client=client
    )


def test_odeon_screening_dates_real_shape():
    client, film = client_and_film()
    client.dates = lambda *args: fixture("dates.json")
    assert client._high_dates(film) == ["2030-01-02", "2030-01-03"]


def test_odeon_distinguishes_advertised_and_film_start():
    client, film = client_and_film()
    client.showtimes = lambda *args: fixture("showtimes.json")
    showing = client._high_showtimes(film, "2030-01-02")[0]
    assert showing.advertised_time == "19:40"
    assert showing.film_time == "20:05"
    assert showing.ends_at.isoformat() == "2030-01-02T22:00:00+00:00"


def test_odeon_preserves_seat_groups_and_accessibility():
    payload = fixture("seats.json")
    client, film = client_and_film()
    from cinema import Showtime

    model = Showtime(
        raw={},
        id="SHOWTIME_ID",
        layout_id="LAYOUT_ID",
        film=film,
        cinema=film.cinema,
        _client=client,
    )
    client.seat_layout = lambda *args: payload
    client.seats = lambda *args: payload["availability"]
    seats = client._high_seats(model)
    assert seats[1].group_ids == ("SEAT_2", "SEAT_3")
    assert seats[1].area_id == "AREA_ID"
    assert [seat.label for seat in model.available_seats()] == ["A1", "A2"]
