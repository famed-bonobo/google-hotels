"""Builds the request arrays of Google Travel's search and prices calls, as Google's own pages send them.

Each page lists its calls in `AF_dataServiceRequests`; these shapes were copied from there and from the filter panel's
own calls (October 2026).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..options import SearchFilters, Stay
from . import constants as config

HOTEL_FILTERS_LENGTH = 11
# Positions inside the hotel part of the filter block.
AMENITIES, CLASSES, FREE_CANCELLATION, SORT, CURRENCY, ECO_CERTIFIED, HOTEL_TYPES = 0, 1, 3, 4, 6, 9, 10
FLAG_ON = 1


def search_request(query: str, stay: Stay, filters: SearchFilters, page_token: str | None) -> list[Any]:
    dates = [None, [None, [_day(stay.check_in), _day(stay.check_out), stay.nights], None, None, None, [None, 0]]]
    guests = [[config.ADULT_GUEST_TYPE]] * stay.adults + [[config.CHILD_GUEST_TYPE, age] for age in stay.children_ages]
    mode = config.SEARCH_MODE_VACATION_RENTALS if filters.is_rentals_search else config.SEARCH_MODE_HOTELS
    page: list[Any] = list(config.FIRST_PAGE)
    page[config.PAGE_TOKEN_INDEX] = page_token
    criteria = [mode, [guests, FLAG_ON if stay.children_ages else 0], dates, None, _filter_block(filters, stay.currency)]
    return [query, criteria, page, []]


def prices_request(property_token: str, stay: Stay) -> list[Any]:
    dates = [_day(stay.check_in), _day(stay.check_out), stay.nights, None, 0]
    options = [None, None, None, stay.currency, dates, *[None] * 8, _guests(stay)]
    return [None, options, [], property_token, config.PRICES_VIEW]


def calendar_request(property_token: str, stay: Stay, first_day: date, last_day: date) -> list[Any]:
    """Google's date picker call: the price of a stay of the same nights and guests for each check-in day."""
    return [None, [_day(first_day), _day(last_day), stay.nights], _guests(stay), property_token, stay.currency]


def reviews_request(property_token: str, size: int, sort: str, source: str, query: str, page_token: str | None) -> list[Any]:
    """The reviews call: [3] how many, [4] order, [5] source (None for every site), [7] text search, [9] next page."""
    return [
        None,
        None,
        None,
        size,
        config.REVIEW_SORT_CODES[sort],
        config.REVIEW_SOURCES[source],
        None,
        query or None,
        property_token,
        page_token,
        None,
        None,
        None,
        '',
    ]


def _guests(stay: Stay) -> list[Any]:
    # Without it Google prices 2 adults: an all-inclusive resort quoted 2,090 for 3 adults instead of 3,211.50.
    # The children part mirrors the search call's guest list.
    children = [[config.CHILD_GUEST_TYPE, age] for age in stay.children_ages]
    return [stay.adults, children or None, FLAG_ON if children else 0]


def _filter_block(filters: SearchFilters, currency: str) -> list[Any]:
    hotel: list[Any] = [None] * HOTEL_FILTERS_LENGTH
    hotel[AMENITIES] = [config.HOTEL_AMENITY_CODES[name] for name in filters.amenities] or None
    hotel[CLASSES] = list(filters.hotel_classes) or None
    hotel[FREE_CANCELLATION] = FLAG_ON if filters.free_cancellation_only else None
    hotel[SORT] = config.SORT_CODES[filters.sort_by]
    hotel[CURRENCY] = currency
    hotel[ECO_CERTIFIED] = FLAG_ON if filters.eco_certified_only else None
    hotel[HOTEL_TYPES] = [config.HOTEL_TYPE_CODES[name] for name in filters.hotel_types] or None
    block: list[Any] = [hotel, None, _rental_filters(filters), _price_filter(filters), None, None]
    block[4] = config.MIN_RATING_CODES[float(filters.min_rating)] if filters.min_rating else None
    block[5] = FLAG_ON if filters.special_offers_only else None
    while block[-1] is None:
        block.pop()
    return block


def _rental_filters(filters: SearchFilters) -> list[Any]:
    if not filters.is_rentals_search:
        return []
    return [
        [config.RENTAL_AMENITY_CODES[name] for name in filters.rental_amenities] or None,
        filters.min_bedrooms,
        filters.min_bathrooms,
        [config.RENTAL_TYPE_CODES[name] for name in filters.rental_types] or None,
    ]


def _price_filter(filters: SearchFilters) -> list[Any] | None:
    # The trailing flag keeps vacation rentals out of a hotel search.
    hotels_only = FLAG_ON if filters.property_mode == 'hotels' else None
    if filters.min_price is None and filters.max_price is None and not hotels_only:
        return None
    return [
        [None, filters.min_price] if filters.min_price is not None else None,
        [None, filters.max_price] if filters.max_price is not None else None,
        hotels_only,
    ]


def _day(day: date) -> list[int]:
    return [day.year, day.month, day.day]
