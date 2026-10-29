"""The wire format: request arrays, the batchexecute envelope, the stay parameter of links, and the filter echo check."""

from __future__ import annotations

import base64
import json
from datetime import date

import pytest

from google_hotels._protocol.batchexecute import encode_call, read_payload
from google_hotels._protocol.filter_check import dropped_filters
from google_hotels._protocol.requests import calendar_request, prices_request, reviews_request, search_request
from google_hotels._protocol.urls import build_hotel_url, build_stay_parameter
from google_hotels.errors import InvalidRequestError
from google_hotels.options import SearchFilters, Stay

from .builders import framed_answer

STAY = Stay(date(2026, 12, 4), date(2026, 12, 6), adults=3, children_ages=(7,), currency='EUR')


def test_search_request_carries_dates_guests_and_filters() -> None:
    filters = SearchFilters(
        sort_by='lowest_price', hotel_classes=(4, 5), amenities=('pool', 'spa'), min_rating=4.5, max_price=300
    )
    query, criteria, page, _ = search_request('hotels in Lisbon', STAY, filters, None)
    assert query == 'hotels in Lisbon'
    assert criteria[0] == 1
    assert criteria[1] == [[[3], [3], [3], [2, 7]], 1]
    assert criteria[2][1][1] == [[2026, 12, 4], [2026, 12, 6], 2]
    hotel_part = criteria[4][0]
    assert hotel_part[0] == [6, 10] and hotel_part[1] == [4, 5] and hotel_part[4] == 3 and hotel_part[6] == 'EUR'
    assert criteria[4][3] == [None, [None, 300], None]
    assert criteria[4][4] == 9
    assert page[1] is None and page[6] == 13


def test_search_request_sends_lists_so_the_echo_check_compares_like_with_like() -> None:
    request = search_request('x', STAY, SearchFilters(hotel_classes=(4, 5)), None)
    assert json.loads(json.dumps(request)) == request


def test_vacation_rental_search_uses_mode_two_and_rental_filters() -> None:
    filters = SearchFilters(property_mode='vacation_rentals', rental_types=('villas',), min_bedrooms=3)
    criteria = search_request('Algarve', STAY, filters, 'page-2')[1]
    assert criteria[0] == 2
    assert criteria[4][2] == [None, 3, None, [10]]


def test_hotels_only_mode_sets_the_trailing_flag() -> None:
    criteria = search_request('Paris', STAY, SearchFilters(property_mode='hotels'), None)[1]
    assert criteria[4][3] == [None, None, 1]


def test_prices_calendar_and_reviews_requests() -> None:
    prices = prices_request('TOKEN', STAY)
    assert prices[3] == 'TOKEN' and prices[4] == 'prices'
    assert prices[1][3] == 'EUR' and prices[1][4] == [[2026, 12, 4], [2026, 12, 6], 2, None, 0]
    assert prices[1][-1] == [3, [[2, 7]], 1]
    calendar = calendar_request('TOKEN', STAY, date(2026, 12, 4), date(2027, 1, 31))
    assert calendar[1] == [[2026, 12, 4], [2027, 1, 31], 2]
    reviews = reviews_request('TOKEN', 200, 'newest', 'google', 'breakfast', 'next')
    assert reviews[3] == 200 and reviews[4] == 2 and reviews[5] == [-1] and reviews[7] == 'breakfast' and reviews[9] == 'next'


def test_stay_parameter_is_url_safe_base64_without_padding() -> None:
    parameter = build_stay_parameter(STAY)
    assert '=' not in parameter and '+' not in parameter and '/' not in parameter
    decoded = base64.urlsafe_b64decode(parameter + '=' * (-len(parameter) % 4))
    assert b'EUR' in decoded
    url = build_hotel_url('TOKEN', STAY, 'en', 'us')
    assert url.startswith('https://www.google.com/travel/hotels/entity/TOKEN?hl=en&gl=us&ts=')


def test_encode_call_nests_the_request_as_a_json_string() -> None:
    envelope = json.loads(encode_call('AtySUc', ['q', [1]]))
    assert envelope == [[['AtySUc', '["q",[1]]', None, '1']]]


def test_read_payload_finds_the_call_row() -> None:
    assert read_payload(framed_answer('lvkpBc', {'a': [1, 2]}), 'lvkpBc') == ({'a': [1, 2]}, None)


def test_read_payload_explains_missing_and_rejected_rows() -> None:
    payload, problem = read_payload('not json', 'lvkpBc')
    assert payload is None and 'prefix' in problem
    rejected = ")]}'\n\n60\n" + json.dumps([['wrb.fr', 'lvkpBc', None, None, None, [13], '1']]) + '\n'
    payload, problem = read_payload(rejected, 'lvkpBc')
    assert payload is None and 'rejected' in problem


def test_read_payload_raises_when_google_calls_the_request_invalid() -> None:
    invalid = ")]}'\n\n60\n" + json.dumps([['wrb.fr', 'yY52ce', None, None, None, [3], '1']]) + '\n'
    with pytest.raises(InvalidRequestError):
        read_payload(invalid, 'yY52ce')


def test_dropped_filters_names_what_google_left_out() -> None:
    request = search_request('x', STAY, SearchFilters(hotel_classes=(4, 5), min_rating=4.0), None)
    kept = [None, [[None, None, None, None, [[None, [4, 5], None, None, None, None, 'EUR'], None, [], None, 8]]]]
    lost = [None, [[None, None, None, None, [[None, None, None, None, None, None, 'EUR']]]]]
    assert dropped_filters(request, kept) == []
    assert dropped_filters(request, lost) == ['hotelClasses', 'minRating']
