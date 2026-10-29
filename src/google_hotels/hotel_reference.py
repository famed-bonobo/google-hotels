"""Reads what a user typed to name a hotel (a Google Hotels link, a property token or the hotel's name) and checks
that a search result is the hotel that was named."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

# Google Hotels links carry the property token after "/entity/", e.g. /travel/hotels/entity/ChcI.../prices.
ENTITY_PATH_PATTERN = re.compile(r'/entity/([A-Za-z0-9_-]+)')
# Property tokens are URL-safe base64 protobufs, such as "ChcIqZGU6Zmyx7J7GgsvZy8xdGQ1MXBrNBAB".
TOKEN_PATTERN = re.compile(r'^C[g-j][A-Za-z0-9_-]{14,}$')
# Words that name the kind of place rather than the place, so "Hotel Arts" and "Arts Hotel" match.
GENERIC_WORDS = {
    'hotel',
    'hotels',
    'the',
    'and',
    'by',
    'resort',
    'inn',
    'suites',
    'apartments',
    'hostel',
    'a',
    'de',
    'la',
    'el',
    'le',
}


class InvalidHotelReferenceError(ValueError):
    """The text names no hotel the scraper can look up."""


@dataclass(frozen=True)
class HotelReference:
    text: str
    property_token: str | None
    name: str | None


def parse_hotel_reference(text: str) -> HotelReference:
    cleaned = text.strip()
    if not cleaned:
        raise InvalidHotelReferenceError('A hotel entry is empty')
    if cleaned.lower().startswith(('http://', 'https://')):
        match = ENTITY_PATH_PATTERN.search(unquote(urlparse(cleaned).path))
        if not match:
            raise InvalidHotelReferenceError(
                f"{cleaned!r} is not a Google Hotels hotel link; open the hotel on Google Hotels and copy that page's link"
            )
        return HotelReference(cleaned, match.group(1), None)
    if TOKEN_PATTERN.match(cleaned):
        return HotelReference(cleaned, cleaned, None)
    return HotelReference(cleaned, None, cleaned)


def names_match(searched: str, found: str) -> bool:
    """True when every distinctive word of one name appears in the other ("The Plaza" in "The Plaza New York")."""
    searched_words, found_words = _distinctive_words(searched), _distinctive_words(found)
    if not searched_words or not found_words:
        return False
    return found_words <= searched_words or searched_words <= found_words


def _distinctive_words(name: str) -> set[str]:
    plain = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower().replace("'", '')
    return {word for word in re.findall(r'[a-z0-9]+', plain) if word not in GENERIC_WORDS}
