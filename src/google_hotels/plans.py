"""Each operation as a plan that names the Google calls it needs and builds its result from their answers, without doing
any network itself, so the sync and the async client run the very same logic.

A plan yields one `Call` and is sent its payload (a failed call is thrown into the plan), or yields a list of calls and
is sent a list of outcomes, each a payload or the exception that call ended with, so one failed hotel does not sink a
whole page.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, TypeVar

from ._parsers.calendar import parse_price_calendar
from ._parsers.city_report import (
    MODE_PRICES,
    MODE_WHEN,
    MODE_WHERE,
    parse_months,
    parse_neighbourhoods,
    parse_prices_by_class,
    report_request,
    report_request_block,
)
from ._parsers.details import parse_hotel_details
from ._parsers.offers import parse_booking_sources
from ._parsers.photos import categories_request, category_page_request, parse_categories, parse_category_page
from ._parsers.reviews import parse_review_page
from ._parsers.search import REVIEWS_INDEX, parse_hotel, parse_reviews, parse_search_results
from ._protocol import constants
from ._protocol.filter_check import dropped_filters
from ._protocol.page_data import value_at
from ._protocol.requests import calendar_request, prices_request, reviews_request, search_request
from ._protocol.urls import build_hotel_url
from .errors import FilterNotAppliedError, HotelNotFoundError
from .hotel_reference import HotelReference, names_match
from .options import SearchFilters, Stay

T = TypeVar('T')
# The search echo names the place Google matched: a Maps feature ID ("0x...:0x...") when it is one property.
MATCHED_FEATURE_PATH = (1, 0, 2, 0, 1, 0, 5)


@dataclass(frozen=True)
class Call:
    rpc_id: str
    request: list[Any]


@dataclass(frozen=True)
class Locale:
    language: str
    country: str


Plan = Generator[Call | list[Call], Any, T]


def search(
    query: str, stay: Stay, filters: SearchFilters, locale: Locale, max_results: int, with_offers: bool
) -> Plan[list[dict[str, Any]]]:
    """Up to `max_results` hotels in Google's order, each with the booking sites' offers when asked."""
    hotels: list[dict[str, Any]] = []
    seen: set[str] = set()
    page_token, empty_pages = None, 0
    while len(hotels) < max_results:
        page = parse_search_results((yield from _filtered_search_page(search_request(query, stay, filters, page_token))))
        new = [hotel for hotel in page.hotels if hotel['propertyToken'] not in seen][: max_results - len(hotels)]
        seen.update(hotel['propertyToken'] for hotel in new)
        records = [
            _search_record(query, len(hotels) + number, hotel, page.location_name, stay, locale)
            for number, hotel in enumerate(new, 1)
        ]
        if with_offers and records:
            outcomes = yield [Call(constants.PRICES_RPC_ID, prices_request(record['propertyToken'], stay)) for record in records]
            for record, outcome in zip(records, outcomes, strict=True):
                _add_page_data(record, outcome, with_offers=True)
        hotels.extend(records)
        empty_pages = 0 if new else empty_pages + 1
        if not page.next_page_token or empty_pages >= constants.MAX_PAGES_WITHOUT_NEW_HOTELS:
            break
        page_token = page.next_page_token
    return hotels


def hotel(reference: HotelReference, stay: Stay, filters: SearchFilters, locale: Locale) -> Plan[dict[str, Any]]:
    """One hotel's page: its details, every booking site's offer and the lowest of them."""
    token, matched_by = yield from _resolve(reference, stay, filters)
    payload = yield Call(constants.PRICES_RPC_ID, prices_request(token, stay))
    found = parse_hotel(value_at(payload, 0) or [])
    if not found['name']:
        raise HotelNotFoundError(f'Google has no hotel page for {reference.text!r}')
    record = {
        'query': reference.text,
        'matchedBy': matched_by,
        **found,
        'propertyToken': token,
        **_stay_fields(token, stay, locale),
    }
    _add_page_data(record, payload, with_offers=True)
    items = [item for category in (record.get('amenitiesByCategory') or {}).values() for item in category]
    # A hotel page has no card highlights, so its full amenity list by category stands in for them.
    record['amenities'] = sorted({item['name'] for item in items if item['available']})
    record['unavailableAmenities'] = sorted({item['name'] for item in items if not item['available']})
    return record


def for_hotel(reference: HotelReference, stay: Stay, build: Callable[[str], Plan[T]]) -> Plan[T]:
    """Find the hotel's property token first when it was named, then run the plan `build` makes for that token."""
    token, _matched_by = yield from _resolve(reference, stay, SearchFilters())
    return (yield from build(token))


def price_calendar(token: str, stay: Stay, days: int) -> Plan[list[dict[str, Any]]]:
    """The price of the same stay for each check-in day from the stay's check-in on."""
    last_day = stay.check_in + timedelta(days=days - 1)
    payload = yield Call(constants.CALENDAR_RPC_ID, calendar_request(token, stay, stay.check_in, last_day))
    return parse_price_calendar(payload)


def reviews(token: str, limit: int, sort: str, source: str, query: str, today: date) -> Plan[list[dict[str, Any]]]:
    """Up to `limit` reviews, page after page of up to 200."""
    found: list[dict[str, Any]] = []
    page_token = None
    while len(found) < limit:
        size = min(constants.REVIEWS_PER_CALL, limit - len(found))
        page = parse_review_page(
            (yield Call(constants.REVIEWS_RPC_ID, reviews_request(token, size, sort, source, query, page_token))), today
        )
        found.extend(page.reviews)
        if not page.reviews or not page.next_page_token:
            break
        page_token = page.next_page_token
    return found[:limit]


def photos(token: str, hotel_name: str, limit: int) -> Plan[list[dict[str, Any]]]:
    """Up to `limit` photos, first an even share of each category so a gallery is not all bedrooms, then the rest."""
    categories = [
        _Category(code, page_token)
        for code, page_token in parse_categories((yield Call(constants.PHOTO_CATEGORIES_RPC_ID, categories_request(token))))
    ]
    gallery: dict[str, dict[str, Any]] = {}
    share = -(-limit // len(categories)) if categories else 0
    for quota in (share, limit):
        for category in categories:
            yield from _take_from_category(token, hotel_name, category, gallery, quota, limit)
    return list(gallery.values())[:limit]


def city_report(query: str, stay: Stay, filters: SearchFilters) -> Plan[dict[str, Any] | None]:
    """Google's three tabs next to the hotel list: prices by star class, when to visit, and where to stay."""
    block = report_request_block((yield Call(constants.SEARCH_RPC_ID, search_request(query, stay, filters, None))))
    if block is None:
        return None
    prices, months, places = yield [
        Call(constants.CITY_REPORT_RPC_ID, report_request(query, block, mode)) for mode in (MODE_PRICES, MODE_WHEN, MODE_WHERE)
    ]
    for outcome in (prices, months, places):
        if isinstance(outcome, Exception):
            raise outcome
    month_rows, seasons = parse_months(months)
    return {
        'query': query,
        'currency': stay.currency,
        'pricesByHotelClass': parse_prices_by_class(prices),
        'months': month_rows,
        'seasons': seasons,
        'neighbourhoods': parse_neighbourhoods(places),
    }


@dataclass
class _Category:
    """One photo category and where its paging stopped, so the second pass continues instead of starting over."""

    code: Any
    page_token: str | None
    taken: int = 0
    is_done: bool = False

    def __post_init__(self) -> None:
        self.waiting: list[dict[str, Any]] = []


def _take_from_category(
    token: str,
    hotel_name: str,
    category: _Category,
    gallery: dict[str, dict[str, Any]],
    quota: int,
    limit: int,
) -> Plan[None]:
    while category.taken < quota and len(gallery) < limit:
        if not category.waiting:
            if category.is_done or not category.page_token:
                return
            payload = yield Call(constants.PHOTOS_RPC_ID, category_page_request(token, category.code, category.page_token))
            kept, category.page_token = parse_category_page(payload, category.code, hotel_name)
            category.waiting.extend(kept)
            category.is_done = not kept or not category.page_token
            continue
        photo = category.waiting.pop(0)
        if photo['url'] not in gallery:
            gallery[photo['url']] = photo
            category.taken += 1


def _filtered_search_page(request: list[Any]) -> Plan[Any]:
    """Ask again when Google drops one of the filters; its unfiltered answer would put wrong hotels in the results."""
    dropped: list[str] = []
    for _attempt in range(constants.MAX_FILTER_ATTEMPTS):
        payload = yield Call(constants.SEARCH_RPC_ID, request)
        dropped = dropped_filters(request, payload)
        if not dropped:
            return payload
    raise FilterNotAppliedError(f'Google kept ignoring the filters {dropped} after {constants.MAX_FILTER_ATTEMPTS} attempts')


def _resolve(reference: HotelReference, stay: Stay, filters: SearchFilters) -> Plan[tuple[str, str]]:
    if reference.property_token:
        return reference.property_token, 'link' if reference.text != reference.property_token else 'token'
    payload = yield Call(constants.SEARCH_RPC_ID, search_request(reference.name or '', stay, filters, None))
    hotels = parse_search_results(payload).hotels
    if not hotels:
        raise HotelNotFoundError(f'Google found no hotel for {reference.name!r}')
    first = hotels[0]
    matched_feature = value_at(payload, *MATCHED_FEATURE_PATH)
    if isinstance(matched_feature, str) and matched_feature == first.get('googleFeatureId'):
        return first['propertyToken'], 'place'
    if names_match(reference.name or '', first['name'] or ''):
        return first['propertyToken'], 'name'
    # A guess would return the wrong hotel's prices under the name the caller gave.
    raise HotelNotFoundError(
        f'Google found no hotel named {reference.name!r}; its first result was {first["name"]!r}. '
        "Add the city to the name, or pass the hotel's Google Hotels link."
    )


def _add_page_data(record: dict[str, Any], outcome: Any, with_offers: bool) -> None:
    """Add the hotel page's details and every booking site's offer; a failed page leaves the offers as None."""
    if isinstance(outcome, Exception):
        record['bookingSources'] = None
        record['lowestOfferRatePerNight'] = None
        return
    record.update(parse_hotel_details(outcome))
    if with_offers:
        sources = parse_booking_sources(outcome)
        rates = [source['ratePerNight'] for source in sources if source['ratePerNight'] is not None]
        record['bookingSources'] = sources
        # Google leaves some hotels without a price in the list even though booking sites offer them.
        record['lowestOfferRatePerNight'] = min(rates) if rates else None
    if record.get('overallRating') is None and record.get('reviewsCount') is None:
        # Some answers come without the review block in the list; the hotel's own page still carries it.
        found = parse_reviews(value_at(outcome, 0, REVIEWS_INDEX))
        if found['overallRating'] is not None or found['reviewsCount'] is not None:
            record.update(found)


def _search_record(
    query: str, position: int, found: dict[str, Any], location: str | None, stay: Stay, locale: Locale
) -> dict[str, Any]:
    return {
        'query': query,
        'position': position,
        **found,
        'searchLocation': location,
        **_stay_fields(found['propertyToken'], stay, locale),
    }


def _stay_fields(token: str, stay: Stay, locale: Locale) -> dict[str, Any]:
    return {
        'googleHotelsUrl': build_hotel_url(token, stay, locale.language, locale.country),
        'checkInDate': stay.check_in.isoformat(),
        'checkOutDate': stay.check_out.isoformat(),
        'nights': stay.nights,
        'adults': stay.adults,
        'scrapedAt': datetime.now(UTC).isoformat(timespec='seconds'),
    }
