"""Every public method against Google itself, to catch a change in Google's answers. Run with: pytest -m live"""

from __future__ import annotations

import pytest

from google_hotels import AsyncGoogleHotels, GoogleHotels

pytestmark = pytest.mark.live


@pytest.fixture(scope='module')
def hotels() -> GoogleHotels:
    with GoogleHotels(currency='EUR') as client:
        yield client


@pytest.fixture(scope='module')
def lisbon(hotels: GoogleHotels) -> list[dict]:
    return hotels.search('hotels in Lisbon', nights=2, max_results=25, with_offers=True, min_rating=4.0)


@pytest.fixture(scope='module')
def busiest(lisbon: list[dict]) -> dict:
    """The most reviewed hotel of the search: Google's order differs by IP, its review count does not matter."""
    return max(lisbon, key=lambda hotel: hotel['reviewsCount'] or 0)


def test_search_with_offers(lisbon: list[dict]) -> None:
    assert len(lisbon) == 25
    assert all(hotel['propertyToken'] and hotel['name'] for hotel in lisbon)
    assert all(hotel['overallRating'] is None or hotel['overallRating'] >= 4.0 for hotel in lisbon)
    priced = [hotel for hotel in lisbon if hotel['bookingSources']]
    assert len(priced) >= 20
    assert all(source['source'] for hotel in priced for source in hotel['bookingSources'])


def test_star_class_filter_is_applied(hotels: GoogleHotels) -> None:
    found = hotels.search('hotels in Manhattan', max_results=20, hotel_classes=[5])
    assert found and all(hotel['hotelClass'] == 5 for hotel in found)


def test_hotel_by_name(hotels: GoogleHotels) -> None:
    page = hotels.hotel('Hotel Avenida Palace Lisbon', nights=2)
    assert 'Avenida Palace' in page['name'] and page['bookingSources'] and page['address']


def test_price_calendar(hotels: GoogleHotels, busiest: dict) -> None:
    # Sold-out dates have no price, so a busy hotel prices fewer than all 60 days.
    calendar = hotels.price_calendar(busiest, days=60, nights=2)
    assert len(calendar) >= 30 and any(day['isCheapestDate'] for day in calendar)


def test_reviews(hotels: GoogleHotels, busiest: dict) -> None:
    assert busiest['reviewsCount'] >= 1000
    reviews = hotels.reviews(busiest, limit=250, sort='newest')
    assert len(reviews) == 250 and all(review['rating'] for review in reviews)


def test_photos(hotels: GoogleHotels, busiest: dict) -> None:
    photos = hotels.photos(busiest, limit=20)
    assert photos and all(photo['url'].startswith('https://') for photo in photos)


def test_city_report(hotels: GoogleHotels) -> None:
    report = hotels.city_report('Lisbon', nights=2)
    assert report and report['pricesByHotelClass'] and len(report['months']) == 12


async def test_async_search() -> None:
    async with AsyncGoogleHotels() as client:
        found = await client.search('hotels in Tokyo', max_results=30, with_offers=True)
    assert len(found) == 30 and sum(1 for hotel in found if hotel['bookingSources']) >= 20
