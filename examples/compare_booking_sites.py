"""For each hotel of a search, show which booking site is cheapest and how much it saves against Booking.com.

python examples/compare_booking_sites.py "hotels in Barcelona"
"""

import sys

from google_hotels import GoogleHotels

query = sys.argv[1] if len(sys.argv) > 1 else 'hotels in Barcelona'

with GoogleHotels(currency='EUR') as hotels:
    found = hotels.search(query, nights=2, max_results=20, with_offers=True)

for hotel in found:
    offers = [offer for offer in hotel['bookingSources'] or [] if offer['totalRate'] is not None]
    if not offers:
        continue
    cheapest = min(offers, key=lambda offer: offer['totalRate'])
    booking = next((offer for offer in offers if offer['source'] == 'Booking.com'), None)
    difference = booking['totalRate'] - cheapest['totalRate'] if booking else 0
    saving = f', {difference:.0f} less than Booking.com' if difference > 0 else ''
    print(f'{hotel["name"]}: {cheapest["source"]} {cheapest["totalRate"]:.0f} EUR for 2 nights{saving}')
