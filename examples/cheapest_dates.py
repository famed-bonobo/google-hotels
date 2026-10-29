"""Find the cheapest two-night stays at a hotel over the next three months.

python examples/cheapest_dates.py "Hotel Avenida Palace Lisbon"
"""

import sys

from google_hotels import GoogleHotels

hotel_name = sys.argv[1] if len(sys.argv) > 1 else 'Hotel Avenida Palace Lisbon'

with GoogleHotels(currency='EUR') as hotels:
    calendar = hotels.price_calendar(hotel_name, days=90, nights=2)

calendar.sort(key=lambda day: day['totalRate'])
print(f'Cheapest two-night stays at {hotel_name}:')
for day in calendar[:5]:
    print(f'  {day["checkInDate"]} to {day["checkOutDate"]}: {day["totalRate"]:.2f} {day["currency"]}')
print(f'Most expensive: {calendar[-1]["checkInDate"]}, {calendar[-1]["totalRate"]:.2f} {calendar[-1]["currency"]}')
