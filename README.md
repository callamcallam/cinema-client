# cinema-client

One unofficial Python interface for ODEON UK and Vue UK.

```bash
pip install cinema-client
```

```python
from cinema import Cinema

with Cinema.Odeon(site_id="ODEON_SITE_ID") as odeon:
    films = odeon.films()

with Cinema.Vue() as vue:
    films = vue.films("VUE_CINEMA_ID")
```

Both clients expose `cinemas()`, `films()`, `dates()`, `showtimes()`, `seats()`,
`tickets()`, `create_order()`, and `cancel_order()`; provider-specific arguments
reflect each underlying API.

## Full flow

The demo progressively shows cinemas, films, dates, showtimes, prices, and seats:

```bash
python examples/full_flow.py odeon --cinema SITE --film FILM --date YYYY-MM-DD --showtime SHOWTIME --layout LAYOUT
python examples/full_flow.py vue --cinema CINEMA --film FILM --date YYYY-MM-DD --showtime SESSION
```

ODEON reservation and guaranteed cleanup:

```python
with Cinema.Odeon(site_id="SITE") as api:
    created = api.create_order()
    order_id = created.get("order", created)["id"]
    try:
        seat_ids = ["SEAT"]
        api.set_showtime(order_id, "SHOWTIME", seat_ids)
        tickets = api.make_tickets("TICKET_TYPE", len(seat_ids))
        api.set_showtime(order_id, "SHOWTIME", seat_ids, tickets)
    finally:
        api.cancel_order(order_id)
```

Vue reservation and guaranteed cleanup:

```python
with Cinema.Vue() as api:
    body = api.make_order(
        "CINEMA", "SESSION", "you@example.com",
        {"areaCategoryCode": "AREA", "code": "TICKET", "priceInCents": 1299},
        [{"areaNumber": 1, "rowIndex": 2, "columnIndex": 3}],
    )
    created = api.create_order(body)
    order_id = created["result"]["orderSessionId"]
    try:
        print(api.get_order(order_id))
    finally:
        api.cancel_order(order_id)
```

Not affiliated with ODEON or Vue. Their undocumented APIs can change. Creating
orders temporarily holds real seats—use responsibly and cancel unused orders.
