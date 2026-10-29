"""Parsers: each reads the positions Google uses, and leaves out what it must not return (reviewers, visitors' photos)."""

from __future__ import annotations

from datetime import date

import pytest

from google_hotels import PageFormatError
from google_hotels._parsers.calendar import parse_price_calendar
from google_hotels._parsers.offers import parse_booking_sources
from google_hotels._parsers.photos import parse_categories, parse_category_page
from google_hotels._parsers.reviews import estimate_date, parse_review_page
from google_hotels._parsers.search import parse_search_results

from .builders import nested

HOTEL_KEY, NEXT_KEY = '397419284', '410579159'


def search_entry(name: str, token: str) -> list:
    return nested(
        {
            (1,): name,
            (20,): token,
            (3, 0): '4-star hotel',
            (3, 1): 4,
            (2, 0, 0): 38.71,
            (2, 0, 1): -9.14,
            (2, 17, 0): '3:00 PM',
            (2, 17, 1): '12:00 PM',
            (6, 2, 1, 0): '€84',
            (6, 2, 1, 2): 83.51878,
            (6, 2, 15): 'EUR',
            (6, 2, 44): [140.0, 12.5, 15.0, 167.5],
            (7,): [[4.46, 2140], [[[5, 60, 1300], [4, 25, 540]]]],
            (10, 8): [[1, 1], [0, 2]],
            (5, 1): [[None, ['https://img/1']]],
            (9,): '0x1:0x2',
        }
    )


def search_payload(entries: list, next_token: str | None) -> list:
    results = [[None, {HOTEL_KEY: [entry]}] for entry in entries]
    if next_token:
        results.append([None, {NEXT_KEY: [next_token]}])
    return nested({(0, 0, 0, 1): results, (1, 0, 2, 0, 1, 0, 6): 'Lisbon'})


def test_search_results_become_hotel_records() -> None:
    page = parse_search_results(search_payload([search_entry('Hotel A', 'TOKEN_A')], 'NEXT'))
    hotel = page.hotels[0]
    assert page.next_page_token == 'NEXT' and page.location_name == 'Lisbon'
    assert hotel['name'] == 'Hotel A' and hotel['propertyToken'] == 'TOKEN_A' and hotel['hotelClass'] == 4
    assert hotel['ratePerNight'] == 83.52 and hotel['currency'] == 'EUR'
    assert hotel['totalRate'] == 167.5 and hotel['taxesAndFees'] == 27.5 and hotel['fees'] == 15.0
    assert hotel['overallRating'] == 4.5 and hotel['reviewsCount'] == 2140 and hotel['reviewsByStars'] == {'5': 1300, '4': 540}
    assert hotel['checkInTime24h'] == '15:00' and hotel['checkOutTime24h'] == '12:00'
    assert hotel['amenities'] == ['Airport shuttle'] and hotel['unavailableAmenities'] == ['Air conditioning']
    assert hotel['images'] == ['https://img/1'] and hotel['propertyType'] == 'hotel'


def test_search_answer_without_results_is_a_format_error() -> None:
    with pytest.raises(PageFormatError):
        parse_search_results([[]])


def test_booking_sources_keep_sponsored_and_plain_offers_with_rooms() -> None:
    offer = nested(
        {
            (0, 0): 'Booking.com',
            (0, 2): '/travel/lodging/clk?pcurl=https%3A%2F%2Fbooking.com%2Fh',
            (0, 5): False,
            (12, 4, 0): '€90',
            (12, 4, 2): 90.0,
            (12, 5, 2): 180.0,
        }
    )
    sponsored = nested({(0, 0): 'Hotel site', (0, 2): '/aclk?x=1', (0, 5): True, (12, 4, 2): 85.0})
    room = nested({(0,): 'Double room', (2,): [nested({(2,): [True, 'Dec 1'], (4, 2): 92.0, (7,): True})]})
    lister = nested({(0, 0): 'Booking.com', (7,): [room]})
    payload = nested({(0, 6, 2, 21): [offer], (0, 6, 2, 12): [sponsored], (0, 6, 2, 2): [lister]})
    sources = parse_booking_sources(payload)
    assert [source['source'] for source in sources] == ['Booking.com', 'Hotel site']
    booking = sources[0]
    assert booking['partnerUrl'] == 'https://booking.com/h' and booking['isSponsored'] is False
    assert booking['rooms'][0]['rates'][0]['freeCancellationUntil'] == 'Dec 1' and booking['freeCancellationAvailable'] is True
    assert sources[1]['isSponsored'] is True and sources[1]['isOfficialSite'] is True


def test_price_calendar_marks_the_cheapest_dates() -> None:
    def day(check_in: list[int], check_out: list[int], total: float) -> list:
        return nested({(1, 2): total / 2, (8,): [check_in, check_out, 2], (15,): 'EUR', (44,): [total - 20, 15.0, 5.0, total]})

    payload = [None, [day([2026, 12, 5], [2026, 12, 7], 300.0), day([2026, 12, 4], [2026, 12, 6], 250.0), [None]]]
    calendar = parse_price_calendar(payload)
    assert [entry['checkInDate'] for entry in calendar] == ['2026-12-04', '2026-12-05']
    assert calendar[0]['isCheapestDate'] is True and calendar[1]['isCheapestDate'] is False
    assert calendar[0]['taxesAndFees'] == 20.0


def test_reviews_keep_the_review_and_drop_the_reviewer() -> None:
    body = nested(
        {
            (0,): ['Reviewer Name', 'https://profile'],
            (1,): '2 months ago',
            (2,): [5, 5],
            (3, 0, 0, 1): ('(Translated by Google) Great breakfast\n(Original)\nPequeno-almoço ótimo'),
            (5, 0): ['Dear Reviewer Name,', 'Thank you for staying with us.'],
            (5, 1): 'a month ago',
            (6,): [6, 5],
            (7,): [[1, [5]], [5, [4]]],
            (8,): 'review-1',
        }
    )
    review = [['Google'], body]
    page = parse_review_page(nested({(0, 0): [review], (0, 5): 'NEXT'}), date(2026, 10, 29))
    found = page.reviews[0]
    assert page.next_page_token == 'NEXT'
    assert found['text'] == 'Great breakfast' and found['originalText'] == 'Pequeno-almoço ótimo'
    assert found['rating'] == 5 and found['tripPurpose'] == 'vacation' and found['travelGroup'] == 'couple'
    assert found['categoryRatings'] == {'rooms': 5, 'location': 4}
    assert found['hotelReply'] == 'Thank you for staying with us.'
    assert found['publishedAtEstimate'] == '2026-08-30'
    assert 'Reviewer Name' not in repr(found)


@pytest.mark.parametrize(('ago', 'expected'), [('a week ago', '2026-10-22'), ('3 days ago', '2026-10-26'), ('last summer', None)])
def test_relative_review_dates(ago: str, expected: str | None) -> None:
    assert estimate_date(ago, date(2026, 10, 29)) == expected


def test_photos_keep_the_property_and_sites_and_drop_visitors() -> None:
    def photo(url: str, contributor: str, link: str) -> list:
        return nested({(0,): url, (10, 0): contributor, (10, 2): link, (17, 2, 2): [800, 1200], (22, 0): 1760000000})

    page = [
        [
            photo('//lh3/own=w253-h168-k-no', 'Hotel Arts', '//maps/contrib/1'),
            photo('https://site/photo=w253-h168', 'Expedia', 'https://expedia.com'),
            photo('https://visitor/photo', 'A Visitor', '//maps/contrib/2'),
        ],
        'NEXT',
    ]
    agoda = nested({(0,): 'https://lh6/proxy/x', (14,): [1, 'http://pix8.agoda.net/hotelImages/1.jpg'], (17, 2, 2): [500, 700]})
    page[0].append(agoda)
    photos, token = parse_category_page(page, 6, 'Hotel Arts')
    assert token == 'NEXT' and [entry['source'] for entry in photos] == ['property', 'Expedia', 'Agoda']
    assert photos[2]['url'] == 'https://pix8.agoda.net/hotelImages/1.jpg'
    assert photos[0]['url'] == 'https://lh3/own=w1200-h800-k-no' and photos[0]['category'] == 'Bedroom'
    assert 'A Visitor' not in repr(photos)


def test_photo_categories_put_the_mixed_one_last() -> None:
    payload = nested({(1, 7): [[1, None, 'P1'], [6, None, 'P6'], [5, None, 'P5']]})
    assert parse_categories(payload) == [(6, 'P6'), (5, 'P5'), (1, 'P1')]
