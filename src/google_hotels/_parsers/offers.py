"""Turns the answer of Google Hotels' prices call into booking-site offers, each with its rooms and rate plans."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit

from .._protocol import constants as config
from .._protocol.page_data import money_at, value_at

PRICES_BLOCK_PATH = (0, 6, 2)
# Inside the prices block: the "all options" list, the sponsored offers Google shows on top, and the sites that list
# their rooms. A site can appear in only one of them, so all three are read (checked 2026-10-16: Expedia.de in
# Berlin and Expedia.com in New York were only among the room listers).
ALL_OFFERS_INDEX = 21
SPONSORED_OFFERS_INDEX = 12
ROOM_PROVIDERS_INDEX = 2
# Google's ad click URLs start with this path; plain listings use /travel/lodging/clk.
AD_CLICK_PATH = '/aclk'
# The booking site's own URL rides in this parameter of Google's click URL.
PARTNER_URL_PARAMETER = 'pcurl'


def parse_booking_sources(payload: Any) -> list[dict[str, Any]]:
    block = value_at(payload, *PRICES_BLOCK_PATH)
    if not isinstance(block, list):
        return []
    providers = [entry for entry in value_at(block, ROOM_PROVIDERS_INDEX) or [] if _source_name(entry)]
    rooms_by_source = {_source_name(entry): _parse_rooms(value_at(entry, 7)) for entry in providers}
    offers: list[dict[str, Any]] = []
    seen: set[tuple[str, bool]] = set()
    for entry in [*(value_at(block, ALL_OFFERS_INDEX) or []), *(value_at(block, SPONSORED_OFFERS_INDEX) or [])]:
        offer = _parse_offer(entry)
        # A site can be both a sponsored offer and a plain listing; Google shows both, so both are kept.
        key = (offer['source'], offer['isSponsored'])
        if offer['source'] and key not in seen:
            seen.add(key)
            offers.append(_with_rooms(offer, entry, rooms_by_source))
    listed = {offer['source'] for offer in offers}
    offers += [
        _with_rooms(_parse_offer(entry), entry, rooms_by_source) for entry in providers if _source_name(entry) not in listed
    ]
    return offers


def _with_rooms(
    offer: dict[str, Any], entry: list[Any], rooms_by_source: dict[str | None, list[dict[str, Any]]]
) -> dict[str, Any]:
    # Sponsored offers carry their rooms inline; other offers get them from the room listers by site name.
    rooms = _parse_rooms(value_at(entry, 7)) or rooms_by_source.get(offer['source'], [])
    return {**offer, 'rooms': rooms, 'freeCancellationAvailable': _any_free_cancellation(rooms)}


def _parse_offer(entry: list[Any]) -> dict[str, Any]:
    logo = value_at(entry, 0, 3, 0)
    click_path = value_at(entry, 0, 2)
    member_rate = value_at(entry, 12, 11)
    return {
        'source': _source_name(entry),
        'isOfficialSite': value_at(entry, 0, 5) is True,
        'isSponsored': isinstance(click_path, str) and click_path.startswith(AD_CLICK_PATH),
        'ratePerNight': money_at(entry, 12, 4, 2),
        'ratePerNightDisplay': value_at(entry, 12, 4, 0),
        'totalRate': money_at(entry, 12, 5, 2),
        'totalRateDisplay': value_at(entry, 12, 5, 0),
        # Price for members who sign up for free, with Google's label such as "Member discount".
        'memberRatePerNight': money_at(member_rate, 0, 2),
        'memberTotalRate': money_at(member_rate, 7, 2),
        'memberRateLabel': value_at(member_rate, 1, 0, 0),
        'bookingUrl': _google_url(click_path),
        'partnerUrl': _partner_url(click_path),
        'logo': f'https:{logo}' if isinstance(logo, str) and logo.startswith('//') else logo,
    }


def _parse_rooms(rooms: Any) -> list[dict[str, Any]]:
    parsed = []
    for room in rooms if isinstance(rooms, list) else []:
        images = [value_at(image, 0) for image in value_at(room, 1) or []]
        parsed.append(
            {
                'name': value_at(room, 0),
                'images': [url for url in images if isinstance(url, str)],
                'rates': [_parse_rate(rate) for rate in value_at(room, 2) or []],
            }
        )
    return parsed


def _parse_rate(rate: list[Any]) -> dict[str, Any]:
    # Fields checked against the labels on Google's prices page on 2026-10-16: [2] reads "Free cancellation
    # until Dec 8" when it is [true, "Dec 8"], and [7] is true on the rates labeled "breakfast".
    return {
        'ratePerNight': money_at(rate, 4, 2),
        'ratePerNightDisplay': value_at(rate, 4, 0),
        'totalRate': money_at(rate, 5, 2),
        'totalRateDisplay': value_at(rate, 5, 0),
        'freeCancellation': value_at(rate, 2, 0) is True,
        'freeCancellationUntil': value_at(rate, 2, 1),
        'breakfastIncluded': value_at(rate, 7) is True,
        'bookingUrl': _google_url(value_at(rate, 0)),
    }


def _any_free_cancellation(rooms: list[dict[str, Any]]) -> bool | None:
    rates = [rate for room in rooms for rate in room['rates']]
    return any(rate['freeCancellation'] for rate in rates) if rates else None


def _source_name(entry: Any) -> str | None:
    name = value_at(entry, 0, 0)
    return name if isinstance(name, str) else None


def _google_url(path: Any) -> str | None:
    return f'{config.GOOGLE_ORIGIN}{path}' if isinstance(path, str) else None


def _partner_url(path: Any) -> str | None:
    if not isinstance(path, str):
        return None
    values = parse_qs(urlsplit(path).query).get(PARTNER_URL_PARAMETER)
    return values[0] if values else None
