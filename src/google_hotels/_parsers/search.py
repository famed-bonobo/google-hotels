"""Turns the answer of Google Hotels' search call into hotel records and the token for the next page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .._protocol import constants as config
from .._protocol.page_data import money_at, value_at
from ..errors import PageFormatError
from .amenity_names import CARD_AMENITIES, DETAIL_AMENITIES
from .localized_text import to_24_hour_time, to_minutes

STAR_DISTRIBUTION_ROW_LENGTH = 3
# Vacation rentals carry an extra block: the listing title, capacity [_, guests, bedrooms, bathrooms] and the advertiser.
RENTAL_BLOCK_INDEX = 19
# The review block, [[rating, count], [star distribution]], has this position in search cards and in hotel pages.
REVIEWS_INDEX = 7
# Google's copy of the request names the place it searched.
SEARCHED_LOCATION_PATH = (1, 0, 2, 0, 1, 0, 6)
PROPERTY_TYPE_HOTEL = 'hotel'
PROPERTY_TYPE_VACATION_RENTAL = 'vacationRental'
# Location scores out of 5, checked against the Location tab of hotel pages on 2026-10-16.
LOCATION_SCORE_NAMES = {4: 'overall', 1: 'thingsToDo', 5: 'restaurants', 2: 'transit', 3: 'airportAccess'}


@dataclass(frozen=True)
class SearchPage:
    hotels: list[dict[str, Any]]
    next_page_token: str | None
    # The place Google understood the search to be about, such as "Faro District" for "vacation rentals in Algarve".
    location_name: str | None


def parse_search_results(payload: Any) -> SearchPage:
    results = value_at(payload, 0, 0, 0, 1)
    if not isinstance(results, list):
        raise PageFormatError('The search answer has no result list where Google normally puts it')
    hotels = [parse_hotel(entry) for entry in _results_with_key(results, config.HOTEL_RESULT_KEY)]
    next_tokens = [value_at(entry, 0) for entry in _results_with_key(results, config.NEXT_PAGE_KEY)]
    next_page_token = next(iter(token for token in next_tokens if token), None)
    location = value_at(payload, *SEARCHED_LOCATION_PATH)
    return SearchPage(
        hotels=[hotel for hotel in hotels if hotel['propertyToken']],
        next_page_token=next_page_token,
        location_name=location if isinstance(location, str) else None,
    )


def parse_hotel(entry: list[Any]) -> dict[str, Any]:
    price = value_at(entry, 6, 2) or []
    # Google splits the stay as [before taxes, taxes, mandatory fees such as resort or cleaning fees, total].
    stay_breakdown = value_at(price, 44) or []
    total_rate = money_at(stay_breakdown, 3)
    before_taxes = money_at(stay_breakdown, 0)
    rental = value_at(entry, RENTAL_BLOCK_INDEX)
    listing_title = value_at(rental, 6)
    check_in, check_out = _clean_text(value_at(entry, 2, 17, 0)), _clean_text(value_at(entry, 2, 17, 1))
    deal_label, deal_description = _parse_deal(value_at(price, 7, 3))
    return {
        # For a vacation rental, entry[1] is the advertiser; Google shows the listing title instead.
        'name': listing_title if isinstance(listing_title, str) else value_at(entry, 1),
        'propertyType': PROPERTY_TYPE_VACATION_RENTAL if rental else PROPERTY_TYPE_HOTEL,
        'listedBy': value_at(entry, 1) if rental else None,
        'sleeps': value_at(rental, 1, 1),
        'bedrooms': value_at(rental, 1, 2),
        'bathrooms': value_at(rental, 1, 3),
        'beds': value_at(rental, 1, 4),
        'propertyToken': value_at(entry, 20),
        'hotelClass': value_at(entry, 3, 1),
        'hotelClassText': value_at(entry, 3, 0),
        'description': value_at(entry, 11, 0),
        'website': value_at(entry, 2, 29, 2),
        'latitude': value_at(entry, 2, 0, 0),
        'longitude': value_at(entry, 2, 0, 1),
        **parse_reviews(value_at(entry, REVIEWS_INDEX)),
        'checkInTime': check_in,
        'checkOutTime': check_out,
        'checkInTime24h': to_24_hour_time(check_in),
        'checkOutTime24h': to_24_hour_time(check_out),
        'currency': value_at(price, 15),
        'ratePerNight': money_at(price, 1, 2),
        'ratePerNightDisplay': value_at(price, 1, 0),
        'totalRate': total_rate,
        'totalRateBeforeTaxesAndFees': before_taxes,
        'taxesAndFees': round(total_rate - before_taxes, 2) if total_rate is not None and before_taxes is not None else None,
        'taxes': money_at(stay_breakdown, 1),
        'fees': money_at(stay_breakdown, 2),
        'dealLabel': deal_label,
        'dealDescription': deal_description,
        'amenities': _card_amenities(value_at(entry, 10, 8), available=True),
        'unavailableAmenities': _card_amenities(value_at(entry, 10, 8), available=False),
        'locationScores': _location_scores(value_at(entry, 2, 12, 5)),
        'nearbyPlaces': _parse_nearby_places(value_at(entry, 2, 19)),
        'thumbnail': value_at(entry, 12, 0),
        'images': _parse_images(value_at(entry, 5, 1)),
        'googleFeatureId': value_at(entry, 9),
    }


def parse_reviews(block: Any) -> dict[str, Any]:
    return {
        'overallRating': _rating(value_at(block, 0, 0)),
        'reviewsCount': value_at(block, 0, 1),
        'reviewsByStars': _parse_star_distribution(value_at(block, 1, 0)),
    }


def _card_amenities(items: Any, available: bool) -> list[str]:
    # Each item is [available, code]. Cards and hotel pages share the code space (the codes both name match), so a
    # card code without a card label takes the hotel-page name; an unknown code is kept as "amenity <code>".
    names = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, list) and len(item) >= 2 and bool(item[0]) is available:
            names.append(CARD_AMENITIES.get(item[1]) or DETAIL_AMENITIES.get(item[1]) or f'amenity {item[1]}')
    return names


def _location_scores(scores: Any) -> dict[str, float] | None:
    parsed = {}
    for score in scores if isinstance(scores, list) else []:
        name = LOCATION_SCORE_NAMES.get(value_at(score, 0))
        value = value_at(score, 1)
        if name and isinstance(value, str):
            try:
                parsed[name] = float(value)
            except ValueError:
                continue
    return parsed or None


def _parse_deal(deal: Any) -> tuple[str | None, str | None]:
    """Google's price badge ("25% less than usual", "Great price · with pool"); its position varies by badge kind."""
    if not isinstance(deal, list):
        return None, None
    badges = [item for item in deal if isinstance(item, list) and item and isinstance(item[0], str)]
    if not badges:
        return None, None
    label, description = badges[-1][0], value_at(badges[-1], 1)
    return label, description if isinstance(description, str) else None


def _results_with_key(results: list[Any], key: str) -> list[Any]:
    entries = []
    for result in results:
        payload = value_at(result, 1)
        if isinstance(payload, dict) and key in payload:
            entries.append(value_at(payload, key, 0) if key == config.HOTEL_RESULT_KEY else payload[key])
    return [entry for entry in entries if entry]


def _parse_star_distribution(rows: Any) -> dict[str, int] | None:
    if not isinstance(rows, list):
        return None
    distribution = {}
    for row in rows:
        if isinstance(row, list) and len(row) >= STAR_DISTRIBUTION_ROW_LENGTH:
            stars, _percent, count = row[:STAR_DISTRIBUTION_ROW_LENGTH]
            distribution[str(stars)] = count
    return distribution or None


def _parse_nearby_places(groups: Any) -> list[dict[str, Any]]:
    places = []
    for group in groups if isinstance(groups, list) else []:
        for place in value_at(group, 1, 2) or []:
            transportations = [
                {
                    'mode': config.TRANSPORT_MODES.get(value_at(option, 0), 'other'),
                    'duration': value_at(option, 1),
                    'durationMinutes': to_minutes(value_at(option, 1)),
                }
                for option in value_at(place, 2) or []
            ]
            places.append({'name': value_at(place, 0), 'transportations': transportations})
    return places


def _parse_images(images: Any) -> list[str]:
    urls = [value_at(image, 1, 0) for image in images if isinstance(image, list)] if isinstance(images, list) else []
    return [url for url in urls if isinstance(url, str)]


def _rating(value: Any) -> float | None:
    # Vacation rentals come with long averages such as 3.5954773; Google shows them with one decimal.
    return round(value, 1) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _clean_text(value: Any) -> str | None:
    # Google separates the time from AM/PM with a narrow no-break space, which breaks naive string matching.
    return value.replace(' ', ' ') if isinstance(value, str) else None
