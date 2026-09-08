# cinema-client

Unofficial Python clients for exploring the public web APIs used by ODEON UK
and Vue UK.

```bash
pip install cinema-client
```

```python
from cinema import Cinema

with Cinema.Odeon() as api:
    cinema = api.search("your city")
    film = cinema.film("film title")
    showing = film.time("8pm", "tomorrow")
    seats = showing.best_seats(2)
```

The same high-level flow works with `Cinema.Vue()`. Low-level methods, raw
provider payloads, search, showtimes, seats, tickets, temporary orders and order
cancellation are also available.

## Educational use only

This project is unofficial, educational software and is not affiliated with or
endorsed by ODEON or Vue. Use it only where you have permission and in accordance
with applicable laws and provider terms. Do not disrupt booking availability,
other customers, accounts or services.

The software is provided “as is”, without warranty. Users are responsible for
their own actions and any consequences arising from use or misuse. Provider APIs
are undocumented and may change without notice.

Creating an order can temporarily hold real seats. Cancel any order you do not
intend to complete. Tests and development should use mocks rather than live
inventory.
