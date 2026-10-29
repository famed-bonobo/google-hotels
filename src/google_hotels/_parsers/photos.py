"""Reads Google Hotels' photos tab: the categories, and each page of a category's photos at full size.

Visitors' photos are left out: they can show people and they name the person who took them. Within a category the
property's and the booking sites' photos come first and the visitors' after them, so a page with none of the former
ends the category.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from .._protocol import constants
from .._protocol.page_data import value_at
from ..hotel_reference import names_match

THUMBNAIL_SIZE = [253, 253]
COVER_PHOTOS = 26
CATEGORIES_PATH = (1, 7)
# One photo: [0] thumbnail, [5] caption, [10] [contributor, avatar, link], [14] [kind, original URL],
# [17][2][2] [height, width], [22] [seconds since 1970 when it was added].
THUMBNAIL, CAPTION, CONTRIBUTOR, ORIGINAL, SIZE_PATH, ADDED_PATH = 0, 5, 10, 14, (17, 2, 2), (22, 0)
ORIGINAL_IS_URL = 1
# Google-hosted images take their size in the URL suffix ("=w253-h168-k-no").
SIZE_SUFFIX = re.compile(r'=w\d+-h\d+(-[a-z-]+)?$')
VISITOR_LINK_PART = 'maps/contrib'
# Category codes of Google's photos tab, in the tab's order.
CATEGORY_NAMES = {1: 'At a glance', 6: 'Bedroom', 8: 'Bathroom', 5: 'Exterior', 22: 'Interior', 3: 'Amenities', 4: 'Food & drink'}
# "At a glance" mixes the other categories, so it is read last and only adds what they missed.
MIXED_CATEGORY = 1
SOURCE_PROPERTY = 'property'
# Booking sites' full-size photos often come without a contributor; their image servers name the site. They also come
# as http:// links, and these servers answer the same images over https (checked October 2026).
SITE_OF_IMAGE_HOST = {'agoda.net': 'Agoda', 'bstatic.com': 'Booking.com', 'trvl-media.com': 'Expedia', 'tacdn.com': 'Tripadvisor'}


def categories_request(property_token: str) -> list[Any]:
    return [property_token, THUMBNAIL_SIZE, [], None, COVER_PHOTOS, 1]


def category_page_request(property_token: str, category_code: Any, page_token: str) -> list[Any]:
    return [None, page_token, [None, None, None, category_code], THUMBNAIL_SIZE, property_token, None, constants.PHOTOS_PER_CALL]


def parse_categories(payload: Any) -> list[tuple[Any, str | None]]:
    """(category code, first page token) of each category, with the mixed "At a glance" one last."""
    categories = sorted(value_at(payload, *CATEGORIES_PATH) or [], key=lambda category: value_at(category, 0) == MIXED_CATEGORY)
    return [(value_at(category, 0), value_at(category, 2)) for category in categories]


def parse_category_page(payload: Any, category_code: Any, hotel_name: str) -> tuple[list[dict[str, Any]], str | None]:
    """The property's and booking sites' photos on one page of a category, and the next page's token."""
    photos = [_parse_photo(item, category_code, hotel_name) for item in value_at(payload, 0) or []]
    return [photo for photo in photos if photo], value_at(payload, 1)


def _parse_photo(item: list[Any], category: Any, hotel_name: str) -> dict[str, Any] | None:
    contributor, contributor_link = value_at(item, CONTRIBUTOR, 0), value_at(item, CONTRIBUTOR, 2) or ''
    is_site = contributor_link.startswith('http')
    if VISITOR_LINK_PART in contributor_link and not names_match(hotel_name, contributor or ''):
        return None
    thumbnail = value_at(item, THUMBNAIL)
    if not isinstance(thumbnail, str):
        return None
    thumbnail = f'https:{thumbnail}' if thumbnail.startswith('//') else thumbnail
    height, width = value_at(item, *SIZE_PATH, 0), value_at(item, *SIZE_PATH, 1)
    added = value_at(item, *ADDED_PATH)
    url = _full_size_url(item, thumbnail, width, height)
    site = _site_of_image(url)
    return {
        'url': f'https://{url.removeprefix("http://")}' if site and url.startswith('http://') else url,
        'thumbnailUrl': thumbnail,
        'width': width if isinstance(width, int) else None,
        'height': height if isinstance(height, int) else None,
        'category': CATEGORY_NAMES.get(category, f'category {category}'),
        'caption': value_at(item, CAPTION),
        'source': contributor if is_site else site or SOURCE_PROPERTY,
        'addedAt': datetime.fromtimestamp(added, UTC).date().isoformat() if isinstance(added, int) else None,
    }


def _site_of_image(url: str) -> str | None:
    host = urlsplit(url).hostname or ''
    return next((site for domain, site in SITE_OF_IMAGE_HOST.items() if host == domain or host.endswith(f'.{domain}')), None)


def _full_size_url(item: list[Any], thumbnail: str, width: Any, height: Any) -> str:
    if value_at(item, ORIGINAL, 0) == ORIGINAL_IS_URL and isinstance(value_at(item, ORIGINAL, 1), str):
        return str(value_at(item, ORIGINAL, 1))
    if isinstance(width, int) and isinstance(height, int) and SIZE_SUFFIX.search(thumbnail):
        return SIZE_SUFFIX.sub(f'=w{width}-h{height}-k-no', thumbnail)
    return thumbnail
