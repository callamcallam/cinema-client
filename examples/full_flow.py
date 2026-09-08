"""Full capability tour. Live order creation requires --book and confirmation."""

import argparse
import json

from cinema import Cinema


def show(label, value):
    print(f"\n--- {label} ---")
    print(json.dumps(value, indent=2)[:5000])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", choices=("odeon", "vue"))
    parser.add_argument("--cinema")
    parser.add_argument("--film")
    parser.add_argument("--date")
    parser.add_argument("--showtime")
    parser.add_argument("--layout")
    parser.add_argument("--book", action="store_true", help="enable the state-changing example")
    args = parser.parse_args()

    Client = Cinema.Odeon if args.provider == "odeon" else Cinema.Vue
    with Client() as client:
        show("Cinemas", client.cinemas())
        if not args.cinema:
            print("\nPass --cinema to continue to films.")
            return
        show("Films", client.films(args.cinema))
        if not args.film:
            print("\nPass --film to continue to dates.")
            return
        show("Dates", client.dates(args.film, args.cinema) if args.provider == "odeon" else client.dates(args.cinema, args.film))
        if args.date:
            show("Showtimes", client.showtimes(args.film, args.date, args.cinema) if args.provider == "odeon" else client.showtimes(args.cinema, args.film, args.date))
        if args.showtime:
            if args.provider == "odeon":
                show("Tickets", client.tickets(args.showtime))
                show("Seats", client.seats(args.showtime))
                if args.layout:
                    show("Seat layout", client.seat_layout(args.layout))
            else:
                show("Showing", client.showing(args.cinema, args.showtime))
                show("Tickets", client.tickets(args.cinema, args.showtime))
                show("Seats", client.seats(args.cinema, args.showtime))

        if args.book:
            print("\nOrder creation requires provider-specific ticket and seat IDs.")
            print("See README.md for the complete create -> reserve -> cancel snippets.")


if __name__ == "__main__":
    main()

