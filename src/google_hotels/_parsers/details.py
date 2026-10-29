"""Reads the hotel facts that come with the prices call: contact, description, amenities, ratings elsewhere, review topics."""

from __future__ import annotations

from typing import Any

from .._protocol.page_data import value_at
from .amenity_names import CATEGORIES, DETAIL_AMENITIES, DETAIL_AMENITIES_ABSENT, QUALIFIERS

HOTEL_PATH = (0,)
# Positions checked against Google's hotel page on 2026-10-16 (Generator Paris, Grand Hyatt Berlin).
ADDRESS_PATH = (2, 1, 0, 0, 0)
PHONE_PATH = (2, 2, 0)
NEIGHBORHOOD_PATH = (2, 12, 1)
OTHER_SITES_PATH = (7, 4)
REVIEW_TOPICS_PATH = (7, 9)
ABOUT_PARAGRAPHS_PATH = (11, 1)
AMENITY_CATEGORIES_PATH = (10, 6, 0)
INCLUSIVITY_PATH = (10, 0)
LANGUAGES_CATEGORY = 21


def parse_hotel_details(payload: Any) -> dict[str, Any]:
    hotel = value_at(payload, *HOTEL_PATH)
    amenities = _amenities_by_category(value_at(hotel, *AMENITY_CATEGORIES_PATH))
    return {
        'address': _text(value_at(hotel, *ADDRESS_PATH)),
        'phone': _text(value_at(hotel, *PHONE_PATH)),
        'neighborhoodDescription': _text(value_at(hotel, *NEIGHBORHOOD_PATH)),
        'otherSiteRatings': [_other_site(site) for site in value_at(hotel, *OTHER_SITES_PATH) or [] if _text(value_at(site, 0))],
        'reviewTopics': [_topic(topic) for topic in value_at(hotel, *REVIEW_TOPICS_PATH) or [] if _text(value_at(topic, 4))],
        'about': [paragraph for paragraph in value_at(hotel, *ABOUT_PARAGRAPHS_PATH) or [] if _text(paragraph)],
        'amenitiesByCategory': amenities,
        'languagesSpoken': [item['name'] for item in amenities.get(CATEGORIES[LANGUAGES_CATEGORY], []) if item['available']],
        'inclusivity': [label for group in value_at(hotel, *INCLUSIVITY_PATH) or [] for label in _labels(value_at(group, 1))],
    }


def _amenities_by_category(categories: Any) -> dict[str, list[dict[str, Any]]]:
    # [[category, [[available, code, qualifier?], ...]], ...]; unknown codes keep their number so none is lost.
    grouped: dict[str, list[dict[str, Any]]] = {}
    for category in categories if isinstance(categories, list) else []:
        name = CATEGORIES.get(value_at(category, 0), f'category {value_at(category, 0)}')
        for item in value_at(category, 1) or []:
            available, code = value_at(item, 0) is True, value_at(item, 1)
            label = (DETAIL_AMENITIES if available else DETAIL_AMENITIES_ABSENT).get(code) or DETAIL_AMENITIES.get(code)
            grouped.setdefault(name, []).append(
                {
                    'name': label or f'amenity {code}',
                    'available': available,
                    'qualifier': QUALIFIERS.get(value_at(item, 2)),
                }
            )
    return grouped


def _labels(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [value_at(item, 0) for item in items if _text(value_at(item, 0))]


def _other_site(site: list[Any]) -> dict[str, Any]:
    # [name, logo, [rating, out of], number of reviews, sample reviews...]
    return {
        'source': value_at(site, 0),
        'rating': _rounded(value_at(site, 2, 0)),
        'maxRating': value_at(site, 2, 1),
        'reviewsCount': value_at(site, 3),
    }


def _topic(topic: list[Any]) -> dict[str, Any]:
    # [_, sentiment from -1 to 1, mentions, _, name, _, short name, positive mentions, negative mentions, ...]
    return {
        'name': value_at(topic, 4),
        'shortName': value_at(topic, 6),
        'mentions': value_at(topic, 2),
        'positiveMentions': value_at(topic, 7),
        'negativeMentions': value_at(topic, 8),
        'sentiment': _rounded(value_at(topic, 1), digits=2),
    }


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _rounded(value: Any, digits: int = 1) -> float | None:
    # Google sends ratings as floats such as 3.700000047683716.
    return round(value, digits) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
