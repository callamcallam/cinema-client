# cinema-client

One friendly, unofficial Python SDK for ODEON UK and Vue UK.

```bash
pip install cinema-client
```

## 30-second start

```python
from cinema import Cinema

with Cinema.Odeon() as api:
    cinema = api.search("your city")
    film = cinema.film("film title")
    showing = film.time("8pm", "tomorrow")
    seats = showing.best_seats(2)

    print(cinema, film, showing)
    print([seat.label for seat in seats])
```

The same object flow works with `Cinema.Vue()`. Searches accept exact IDs,
names, partial names and fuzzy matches. Ambiguous searches raise
`AmbiguousMatch` instead of prompting or guessing.

## Models and booking

High-level calls return `CinemaLocation`, `Film`, `Showtime`, `Seat`,
`TicketType` and `Booking` objects. Every object retains its provider payload in
`.raw` and supports `.to_dict()`.

```python
booking = showing.book(seats=["A1", "A2"], ticket="adult")
print(booking.order_id)
booking.cancel()
```

Vue requires `email=` when creating an order. Creating an order can temporarily
hold real seats. The SDK refreshes seats before booking and cleans up an ODEON
order if setup fails; it does not cancel a successfully returned booking.

## Raw API

Existing low-level methods remain available:

```python
api.cinemas()
api.films("CINEMA_ID")
api.dates("FILM_ID", "CINEMA_ID")
api.request("GET", "provider/path")
```

Clients expose `.session`, `.provider`, `.capabilities`, configurable timeouts,
session caching for stable listings, `clear_cache()`, and conservative retries
for transient GET failures. Caller-supplied sessions are never closed by the SDK.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

The SDK never calls `input()` or logs authentication tokens. Interactive code
belongs in `examples/`.

Not affiliated with ODEON or Vue. Their undocumented APIs can change. Use the
package responsibly and comply with provider terms.
