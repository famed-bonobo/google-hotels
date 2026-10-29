# google-hotels

[![PyPI](https://img.shields.io/pypi/v/google-hotels)](https://pypi.org/project/google-hotels/)
[![Python](https://img.shields.io/pypi/pyversions/google-hotels)](https://pypi.org/project/google-hotels/)
[![Tests](https://github.com/famed-bonobo/google-hotels/actions/workflows/tests.yml/badge.svg)](https://github.com/famed-bonobo/google-hotels/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**A Google Hotels API for Python.** Search hotels, get the price from every booking site (Booking.com, Expedia,
Agoda, the hotel's own site...), find the cheapest dates with a 300-day price calendar, and read reviews and photos.
No browser, no API key, no account.

```python
from google_hotels import GoogleHotels

with GoogleHotels(currency="EUR") as hotels:
    for hotel in hotels.search("hotels in Lisbon", check_in="2026-12-04", nights=2, min_rating=4.5, with_offers=True):
        print(hotel["name"], hotel["ratePerNight"], [offer["source"] for offer in hotel["bookingSources"]])
```

- **Every booking site's offer** for each hotel, with rooms, rate plans, free cancellation and breakfast.
- **Price calendar:** the price of the same stay for every check-in date up to about 300 days ahead, in one call.
- **All of Google's filters:** price range, guest rating, star class, 19 amenities, hotel types, free cancellation,
  vacation rentals with bedrooms and bathrooms.
- **Reviews** from Google and partner sites, with trip type, category ratings and the hotel's reply. Reviewers'
  names are never returned.
- **Photos** by category at full size, **city report** (prices by star class, best months, neighbourhoods).
- **Fast:** it calls the same internal endpoints Google's own page uses. 20 hotels with every booking site's offer
  took 6.7 s; a 90-day price calendar 0.3 s.
- Sync and **async** clients, a **command line**, type hints, and 59 tests (8 of them against Google itself).

## Install

```bash
pip install google-hotels
```

Python 3.11 or newer. The only dependency is [httpx](https://www.python-httpx.org/).

## What you get

`search()` returns a list of dicts. A hotel from the example above (58 fields in total, trimmed here):

```json
{
  "position": 1,
  "name": "Brown's | Avenue Hotel",
  "hotelClass": 5,
  "overallRating": 4.6,
  "reviewsCount": 283,
  "ratePerNight": 149.15,
  "totalRate": 298.3,
  "currency": "EUR",
  "lowestOfferRatePerNight": 149.15,
  "address": "R. Rodrigues Sampaio 48, 1150-281 Lisboa, Portugal",
  "latitude": 38.7220236,
  "longitude": -9.1456424,
  "checkInTime24h": "15:00",
  "amenities": ["Breakfast", "Free Wi-Fi", "Outdoor pool", "Air conditioning", "Restaurant", "Airport shuttle"],
  "propertyToken": "ChkIhLCQwvjO2IYWGg0vZy8xMXE0bTZieDkyEAE",
  "bookingSources": [
    {"source": "Brown's Avenue", "isOfficialSite": true, "ratePerNight": 149.15, "totalRate": 298.3, "freeCancellationAvailable": true},
    {"source": "Etrip.net", "isOfficialSite": false, "ratePerNight": 151.74, "totalRate": 303.48, "freeCancellationAvailable": null},
    {"source": "Booking.com", "isOfficialSite": false, "ratePerNight": 182.25, "totalRate": 364.5, "freeCancellationAvailable": true},
    {"source": "Expedia.com", "isOfficialSite": false, "ratePerNight": 166.16, "totalRate": 332.31, "freeCancellationAvailable": true}
  ]
}
```

Here the hotel's own site was 33 € cheaper per night than Booking.com for the same two nights.

## Usage

### Search with filters

```python
hotels = GoogleHotels(currency="USD", language="en", country="us")

found = hotels.search(
    "hotels in Manhattan",
    check_in="2026-12-18", check_out="2026-12-21", adults=2, children_ages=[8],
    max_results=60,                    # Google pages through results; up to 1000
    sort_by="lowest_price",            # relevance, lowest_price, highest_rating, most_reviewed
    min_price=100, max_price=400,      # per night, in the client's currency
    min_rating=4.0,                    # 3.5, 4.0 or 4.5
    hotel_classes=[4, 5],
    amenities=["free_wifi", "fitness_center"],
    free_cancellation_only=True,
)
```

Without dates the stay starts 14 days from today, for one night, as Google's own page does. Filters are checked
before any call: a typo such as `amenities=["jacuzzi"]` raises `InvalidOptionError` with the list of valid values.

<details>
<summary>Every filter</summary>

| Argument | Values |
|---|---|
| `property_mode` | `hotels_and_rentals` (default), `hotels`, `vacation_rentals` |
| `sort_by` | `relevance`, `lowest_price`, `highest_rating`, `most_reviewed` |
| `min_price`, `max_price` | whole amounts per night |
| `min_rating` | `3.5`, `4.0`, `4.5` |
| `hotel_classes` | any of `2`, `3`, `4`, `5` |
| `amenities` | `free_wifi`, `free_breakfast`, `restaurant`, `bar`, `kid_friendly`, `pet_friendly`, `free_parking`, `parking`, `ev_charger`, `room_service`, `fitness_center`, `spa`, `pool`, `indoor_pool`, `outdoor_pool`, `air_conditioned`, `wheelchair_accessible`, `beach_access`, `all_inclusive_available` |
| `hotel_types` | `beach_hotels`, `boutique_hotels`, `hostels`, `inns`, `motels`, `spa_hotels`, `bed_and_breakfasts`, `apartment_hotels`, `other` |
| `free_cancellation_only`, `special_offers_only`, `eco_certified_only` | `True` / `False` |
| `rental_types` (vacation rentals) | `apartments`, `chalets`, `cottages`, `houses`, `houseboats`, `villas`, `other` |
| `rental_amenities` (vacation rentals) | `free_wifi`, `fitness_center`, `air_conditioned`, `kid_friendly`, `pool`, `pet_friendly`, `hot_tub`, `kitchen`, `patio_or_deck`, `outdoor_grill`, `crib`, `fireplace` |
| `min_bedrooms`, `min_bathrooms` (vacation rentals) | 1 to 20 |

Google sometimes ignores a filter and answers with unfiltered hotels. The library checks Google's copy of the
request in every answer and asks again when a filter is missing, so results always match the filters you gave.

</details>

### One hotel and every booking site's offer

`hotel()` takes a hotel from `search()`, its Google Hotels link, its property token, or its name with the city:

```python
page = hotels.hotel("Hotel Avenida Palace Lisbon", check_in="2026-12-04", nights=2)
page["lowestOfferRatePerNight"]           # 296.0
for offer in page["bookingSources"]:
    print(offer["source"], offer["ratePerNight"], offer["partnerUrl"])
    for room in offer["rooms"]:
        print("   ", room["name"], [(rate["ratePerNight"], rate["freeCancellation"], rate["breakfastIncluded"]) for rate in room["rates"]])
```

The hotel page also brings the phone, the description, amenities by category, languages spoken, ratings on other
sites and review topics. A name that Google matches to a different hotel raises `HotelNotFoundError` instead of
returning the wrong hotel's prices.

### Cheapest dates: the price calendar

```python
calendar = hotels.price_calendar(page, days=90, nights=2)   # one call, about 0.3 s
cheapest = [day for day in calendar if day["isCheapestDate"]]
# [{'checkInDate': '2027-01-10', 'checkOutDate': '2027-01-12', 'ratePerNight': 111, 'totalRate': 222, ...}]
```

Each day is the price of the same stay (nights and guests) starting that day, as Google's date picker shows it.

### Reviews

```python
reviews = hotels.reviews(page, limit=500, sort="newest", source="google", query="breakfast")
# sort: most_helpful, newest, highest_rating, lowest_rating; source: all or google
```

Each review has the rating, the text (and the original text when Google translated it), the trip purpose and travel
group, ratings for rooms, service and location, and the hotel's reply. The reviewer's name and profile are left out.

### Photos and the city report

```python
photos = hotels.photos(page, limit=50)        # the property's and booking sites' photos, not visitors'
report = hotels.city_report("Lisbon", nights=2)
report["pricesByHotelClass"]   # typical, low and high price for 2- to 5-star hotels
report["months"]               # 12 months with temperatures, crowds and price level
report["neighbourhoods"]       # where to stay, with Google's description and typical price
```

### Async

```python
import asyncio
from google_hotels import AsyncGoogleHotels

async def main():
    async with AsyncGoogleHotels(max_concurrency=5) as hotels:
        cities = ["Lisbon", "Porto", "Madrid", "Seville"]
        results = await asyncio.gather(*(hotels.search(f"hotels in {city}", nights=2, with_offers=True) for city in cities))

asyncio.run(main())
```

### Command line

```bash
google-hotels search "hotels in Lisbon" --check-in 2026-12-04 --nights 2 --min-rating 4.5 --offers --format csv > lisbon.csv
google-hotels calendar "Hotel Avenida Palace Lisbon" --days 90 --nights 2
google-hotels reviews "Hotel Avenida Palace Lisbon" --limit 200 --sort newest
```

## Errors, rate limits and proxies

Every error derives from `GoogleHotelsError`. Calls that Google rate-limits or blocks are retried with a growing
pause; after 5 failed attempts the call raises `GoogleBlockedError`. A search with offers sends one call per hotel,
five at a time by default (`max_concurrency`). From one home IP that pace has worked in testing, but Google limits
how much one IP can ask for. For large or scheduled jobs, pass a rotating proxy:

```python
GoogleHotels(proxy="http://user:password@proxy.example.com:8000")   # socks5:// needs: pip install "google-hotels[socks]"
```

## Running it at scale

If you need thousands of hotels on a schedule without managing proxies or servers, the same data is available as a
hosted [Google Hotels Scraper on Apify](https://apify.com/famed_bonobo/google-hotels-scraper) by the same author.
Its records use the same field names as this library, so code that reads one reads the other. It costs $2 per 1,000
hotels plus $1 per 1,000 hotels with booking-site offers, and runs on Apify's proxies with schedules, webhooks and
exports to CSV, Excel or Google Sheets.

## How it works

Google Hotels' page loads its data from internal `batchexecute` calls. This library sends the same calls with the
same request shapes the page sends, and reads the answers by position. Nothing is rendered, so a search page takes
about a second. The positions were mapped against live pages in October 2026; when Google changes them, the live
tests (`pytest -m live`) show which part broke.

## FAQ

**Is there an official Google Hotels API?** Not for reading results. Google's Hotel Center APIs are for hotels and
booking sites that send their prices to Google.

**Is it allowed?** This library reads the same public pages anyone can open in a browser, and returns no personal
data: reviewers' names and visitors' photos are left out. You are responsible for how you use the data and for
following the terms that apply to you. This project is not affiliated with Google.

**Why are some hotels without offers?** Google shows no price for a hotel that is sold out or not bookable on your
dates; its `ratePerNight` is `None` and `bookingSources` is an empty list. When the offers call itself fails,
`bookingSources` is `None`.

## Development

```bash
pip install -e . pytest pytest-asyncio ruff mypy
pytest              # 51 offline tests
pytest -m live      # 8 tests against Google
ruff check src tests && mypy src
```

Issues and pull requests are welcome.

This library was written with the help of an AI coding agent (Claude, by Anthropic). Every method was run against
Google and the results checked before release.

## License

[MIT](LICENSE)
