from cinema import Cinema
from datetime import datetime
import time
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

VERBOSE = False
MAX_SEATS_PER_ORDER = 10

class OdeonBooker:
    def __init__(self):
        self.api = None        
        self.cinema = None
        self.film = None
        self.showtime = None
        self.site_id = None
        self.film_id = None

    def log(self, msg, level="info"):
        if VERBOSE:
            if level == "error":
                print(f"\033[91m[ERROR] {msg}\033[0m")
            elif level == "debug":
                print(f"\033[90m[DEBUG] {msg}\033[0m")
            else:
                print(f"\033[93m[INFO] {msg}\033[0m")

    def get_valid_input(self, prompt, options=None):
        while True:
            val = input(f"> {prompt}").strip()
            if not val:
                print("✗ Input required")
                continue
            if options and val.lower() not in options:
                print(f"✗ Choose from: {', '.join(options)}")
                continue
            return val

    def clear(self):
        print("\033[H\033[2J", end="")
        sys.stdout.flush()

    def header(self, title):
        self.clear()
        print("═" * 60)
        print(f"  {title}")
        print("═" * 60)

    def select_cinema(self):
        self.header("Select Cinema")
        search = input("> Cinema name (e.g., london): ").strip()
        if not search:
            return False

        # Use a temporary API (no site_id) to list cinemas
        temp_api = Cinema.Odeon()
        try:
            sites_data = temp_api.cinemas()
        except Exception as e:
            self.log(f"Failed to fetch cinemas: {e}", "error")
            return False
        finally:
            temp_api.close()  # clean up

        sites = sites_data.get('sites', [])
        matches = [s for s in sites if search.lower() in s.get('name', {}).get('text', '').lower()]
        if not matches:
            print("✗ No cinema found")
            time.sleep(1)
            return False

        if len(matches) == 1:
            selected = matches[0]
            self.site_id = selected['id']
            self.cinema = selected
            # Create a new API with the correct site_id
            self.api = Cinema.Odeon(site_id=self.site_id)
            print(f"✓ Selected: {selected['name']['text']}")
            time.sleep(0.5)
            return True

        # Multiple matches
        for i, c in enumerate(matches, 1):
            print(f"  {i}. {c['name']['text']}")
        choice = self.get_valid_input("Number: ")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(matches):
                selected = matches[idx]
                self.site_id = selected['id']
                self.cinema = selected
                self.api = Cinema.Odeon(site_id=self.site_id)
                print(f"✓ Selected: {selected['name']['text']}")
                time.sleep(0.5)
                return True
        except:
            pass
        return False

    def select_film(self):
        if not self.api or not self.site_id:
            print("✗ No cinema selected")
            return False

        self.header("Select Film")
        search = input("> Film title: ").strip()
        if not search:
            return False

        try:
            films_data = self.api.films(self.site_id)
            films = films_data.get('films', [])
            matches = [f for f in films if search.lower() in f.get('title', {}).get('text', '').lower()]
            self.log(f"Found {len(matches)} matching films")
        except Exception as e:
            self.log(f"Film search error: {e}", "error")
            traceback.print_exc()
            return False

        if not matches:
            print("✗ No film found")
            time.sleep(1)
            return False

        if len(matches) == 1:
            self.film = matches[0]
            self.film_id = matches[0]['id']
            print(f"✓ Selected: {matches[0]['title']['text']}")
            time.sleep(0.5)
            return True

        for i, f in enumerate(matches, 1):
            print(f"  {i}. {f['title']['text']}")
        choice = self.get_valid_input("Number: ")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(matches):
                self.film = matches[idx]
                self.film_id = matches[idx]['id']
                print(f"✓ Selected: {matches[idx]['title']['text']}")
                time.sleep(0.5)
                return True
        except:
            pass
        return False

    def select_showtime(self):
        if not self.film_id or not self.site_id:
            print("✗ No film or cinema selected")
            return False

        self.header("Select Showtime")

        try:
            dates_data = self.api.dates(self.film_id, self.site_id)
            self.log(f"Dates data: {dates_data}")
        except Exception as e:
            self.log(f"Error getting dates: {e}", "error")
            traceback.print_exc()
            return False

        dates = []
        for item in dates_data.get('filmScreeningDates', []):
            if isinstance(item, dict) and 'businessDate' in item:
                dates.append(item['businessDate'])
            elif isinstance(item, str):
                dates.append(item)

        if not dates:
            print("✗ No showtimes")
            return False

        print("Available dates:")
        for i, d in enumerate(dates, 1):
            try:
                dt = datetime.fromisoformat(d)
                print(f"  {i}. {dt.strftime('%A %d %B %Y')}")
            except:
                print(f"  {i}. {d}")

        choice = self.get_valid_input("Date number: ")
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(dates):
                return False
            selected_date = dates[idx]
        except:
            return False

        try:
            showtimes_data = self.api.showtimes(self.film_id, selected_date, self.site_id)
            self.log(f"Showtimes data: {showtimes_data}")
        except Exception as e:
            self.log(f"Error getting showtimes: {e}", "error")
            traceback.print_exc()
            return False

        showtimes = showtimes_data.get('showtimes', [])
        if not showtimes:
            print("✗ No showtimes on that date")
            return False

        print(f"\nShowtimes on {selected_date}:")
        for i, st in enumerate(showtimes, 1):
            sched = st.get('schedule', {})
            starts = sched.get('startsAt', 'Unknown')
            screen = st.get('screenId', 'Unknown')
            try:
                t = datetime.fromisoformat(starts.replace('Z', '+00:00'))
                print(f"  {i}. {t.strftime('%H:%M')} - Screen {screen}")
            except:
                print(f"  {i}. {starts} - Screen {screen}")

        choice = self.get_valid_input("Showtime number: ")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(showtimes):
                self.showtime = showtimes[idx]
                self.showtime_id = showtimes[idx]['id']
                self.layout_id = showtimes[idx].get('seatLayoutId')
                print(f"✓ Selected showtime: {self.showtime_id}")
                time.sleep(0.5)
                return True
        except:
            pass
        return False

    def get_available(self):
        if not self.showtime_id:
            return []
        try:
            seat_data = self.api.seats(self.showtime_id)
            availability = {item['seatId']: item['status'] for item in seat_data.get('seatAvailabilities', [])}
            layout_id = self.layout_id
            if not layout_id:
                layout_id = self.showtime.get('seatLayoutId')
            if not layout_id:
                self.log("No layout ID found", "error")
                return []
            layout = self.api.seat_layout(layout_id)
            available = []
            for area in layout.get('seatLayout', {}).get('areas', []):
                area_cat = area.get('areaCategoryId', '')
                for row in area.get('rows', []):
                    for seat in row.get('seats', []):
                        sid = seat.get('id')
                        if availability.get(sid) == 'Available':
                            stype = seat.get('type', 'Normal')
                            if stype not in ['Wheelchair', 'Companion']:
                                available.append({
                                    'id': sid,
                                    'label': f"{seat.get('rowLabel', '')}{seat.get('label', '')}",
                                    'row': seat.get('rowLabel', ''),
                                    'col': seat.get('position', {}).get('columnNumber', 0),
                                    'area': area_cat
                                })
            self.log(f"Parsed {len(available)} available seats")
            return available
        except Exception as e:
            self.log(f"Error getting seats: {e}", "error")
            traceback.print_exc()
            return []

    def get_ticket_candidates(self):
        if not self.showtime_id:
            return []
        try:
            prices = self.api.tickets(self.showtime_id)
            valid = []
            for tp in prices.get('ticketPrices', []):
                restrictions = tp.get('restrictions', [])
                if any(r in str(restrictions) for r in ['Member', 'Voucher', 'ThirdParty', 'Reward', 'Subscription']):
                    continue
                price = tp.get('price', {}).get('valueIncludingTax', 0)
                if price <= 0:
                    continue
                valid.append((tp.get('ticketTypeId'), price))
            valid.sort(key=lambda x: x[1])
            seen = set()
            deduped = []
            for tid, price in valid:
                if tid not in seen:
                    seen.add(tid)
                    deduped.append(tid)
            self.log(f"Candidate ticket types: {deduped}")
            return deduped
        except Exception as e:
            self.log(f"Error getting ticket types: {e}", "error")
            traceback.print_exc()
            return []

    def book_chunk(self, ids, labels):
        candidates = self.get_ticket_candidates()
        if not candidates:
            self.log("No valid ticket types", "error")
            return None
        for tt in candidates:
            try:
                self.log(f"Attempting ticket type: {tt}")
                # create_order now works because self.api has site_id
                order = self.api.create_order()
                oid = order.get('order', {}).get('id')
                if not oid:
                    self.log("Failed to get order ID", "error")
                    continue
                self.log(f"Created order: {oid}")
                tickets = self.api.make_tickets(tt, len(ids))
                self.log(f"Made {len(tickets)} tickets")
                result = self.api.set_showtime(oid, self.showtime_id, ids, tickets)
                self.log(f"Set showtime result: {result}")
                return oid
            except Exception as e:
                self.log(f"Error with ticket {tt}: {e}", "error")
                traceback.print_exc()
                try:
                    if 'oid' in locals():
                        self.api.cancel_order(oid)
                        self.log(f"Cancelled order {oid}")
                except:
                    pass
                continue
        self.log("All ticket types failed", "error")
        return None

    def book_all(self):
        self.header("Book ALL (parallel)")
        available = self.get_available()
        if not available:
            print("✗ No seats")
            return
        print(f"Found {len(available)} seats")
        areas = {}
        for s in available:
            areas.setdefault(s['area'], []).append(s)
        chunks = []
        for area_id, seats in areas.items():
            for i in range(0, len(seats), MAX_SEATS_PER_ORDER):
                chunk = seats[i:i+MAX_SEATS_PER_ORDER]
                chunks.append({
                    'area': area_id,
                    'ids': [s['id'] for s in chunk],
                    'labels': [s['label'] for s in chunk]
                })
        print(f"{len(chunks)} orders to place")
        if self.get_valid_input("Proceed? (y/n): ", ['y','n']) != 'y':
            return
        results = []
        lock = threading.Lock()
        def do_book(chunk):
            oid = self.book_chunk(chunk['ids'], chunk['labels'])
            with lock:
                results.append({'success': oid is not None, 'order_id': oid, 'chunk': chunk})
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(do_book, c) for c in chunks]
            for f in as_completed(futures):
                try:
                    f.result()
                except:
                    pass
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        print("\n" + "="*60)
        print(f"✓ {len(successful)} successful, {len(failed)} failed")
        if successful:
            print("Order IDs:")
            for s in successful:
                print(f"  {s['order_id']} ({len(s['chunk']['labels'])} seats)")
            if self.get_valid_input("Cancel ALL? (y/n): ", ['y','n']) == 'y':
                for s in successful:
                    try:
                        self.api.cancel_order(s['order_id'])
                        print(f"✓ Cancelled {s['order_id']}")
                    except Exception as e:
                        print(f"✗ Failed to cancel {s['order_id']}: {e}")
        else:
            print("No orders placed.")

    def auto_select(self):
        count = int(self.get_valid_input("How many seats? "))
        available = self.get_available()
        if len(available) < count:
            print("✗ Not enough seats")
            return
        areas = {}
        for s in available:
            areas.setdefault(s['area'], []).append(s)
        best = None
        for area_id, seats in areas.items():
            if len(seats) < count:
                continue
            rows = {}
            for s in seats:
                rows.setdefault(s['row'], []).append(s)
            for row, row_seats in rows.items():
                row_seats.sort(key=lambda x: x['col'])
                for i in range(len(row_seats) - count + 1):
                    block = row_seats[i:i+count]
                    if all(block[j+1]['col'] == block[j]['col']+1 for j in range(len(block)-1)):
                        best = block
                        break
                if best:
                    break
            if best:
                break
        if not best:
            print("✗ No contiguous block")
            return
        ids = [s['id'] for s in best]
        labels = [s['label'] for s in best]
        print(f"Found: {', '.join(labels)} (Row {best[0]['row']})")
        if self.get_valid_input("Book? (y/n): ", ['y','n']) == 'y':
            oid = self.book_chunk(ids, labels)
            if oid:
                print(f"✓ Booked! Order: {oid}")
                if self.get_valid_input("Cancel? (y/n): ", ['y','n']) == 'y':
                    self.api.cancel_order(oid)
                    print("Cancelled")
            else:
                print("✗ Failed")

    def manual(self):
        self.header("Manual Selection")
        available = self.get_available()
        if not available:
            print("✗ No seats")
            return
        print("Available rows:")
        rows = {}
        for s in available:
            rows.setdefault(s['row'], []).append(s['label'])
        for row, labels in rows.items():
            print(f"  Row {row}: {', '.join(labels[:20])}{'...' if len(labels)>20 else ''}")
        seat_input = input("> Enter seats (e.g., A1, B2-B4): ").strip()
        if not seat_input:
            return
        wanted = []
        for part in seat_input.split(','):
            part = part.strip().upper()
            if '-' in part:
                start, end = part.split('-')
                row = start[0]
                sn = int(start[1:])
                en = int(end[1:])
                for n in range(sn, en+1):
                    wanted.append(f"{row}{n}")
            else:
                wanted.append(part)
        ids = []
        for label in wanted:
            found = next((s['id'] for s in available if s['label'] == label), None)
            if found:
                ids.append(found)
            else:
                print(f"✗ Seat {label} unavailable")
                return
        if len(ids) > MAX_SEATS_PER_ORDER:
            print(f"✗ Max {MAX_SEATS_PER_ORDER} seats per order")
            return
        print(f"Booking {len(ids)} seats: {', '.join(wanted)}")
        if self.get_valid_input("Confirm? (y/n): ", ['y','n']) == 'y':
            oid = self.book_chunk(ids, wanted)
            if oid:
                print(f"✓ Booked! Order: {oid}")
                if self.get_valid_input("Cancel? (y/n): ", ['y','n']) == 'y':
                    self.api.cancel_order(oid)
                    print("Cancelled")
            else:
                print("✗ Failed")

    def run(self):
        self.header("ODEON Booking Demo")
        print("Select cinema → film → showtime → book")
        input("Press Enter to continue...")
        if not self.select_cinema():
            return
        if not self.select_film():
            return
        if not self.select_showtime():
            return
        self.header("Booking Mode")
        print("1. Manual seats")
        print("2. Auto-select N seats")
        print("3. Book ALL seats (parallel)")
        print("4. View seats only")
        mode = self.get_valid_input("Choice (1-4 or q): ", ['1','2','3','4','q'])
        if mode == 'q':
            return
        if mode == '1':
            self.manual()
        elif mode == '2':
            self.auto_select()
        elif mode == '3':
            self.book_all()
        elif mode == '4':
            av = self.get_available()
            rows = {}
            for s in av:
                rows.setdefault(s['row'], []).append(s['label'])
            for row, labels in rows.items():
                print(f"Row {row}: {', '.join(labels)}")
        print("\n✓ Done")

if __name__ == "__main__":
    OdeonBooker().run()