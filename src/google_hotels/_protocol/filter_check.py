"""Checks that Google applied every filter of a search call, using the copy of the request it sends back.

Google sometimes drops a filter (measured 2026-10-16: the hostels filter was ignored in 2 of 8 identical calls) and
answers with unfiltered hotels. Its answer repeats the filters it used in payload[1][0][4], so a dropped one shows.
"""

from __future__ import annotations

from typing import Any

from .page_data import value_at

ECHOED_FILTERS_PATH = (1, 0, 4)
SENT_FILTERS_PATH = (1, 4)
HOTEL_PART = 0
# Readable names for the error message, by position in the hotel part and in the whole filter block.
HOTEL_FILTER_NAMES = {
    0: 'amenities',
    1: 'hotelClasses',
    3: 'freeCancellationOnly',
    4: 'sortBy',
    9: 'ecoCertifiedOnly',
    10: 'hotelTypes',
}
BLOCK_FILTER_NAMES = {2: 'vacation rental filters', 3: 'price or hotels-only filter', 4: 'minRating', 5: 'specialOffersOnly'}


def dropped_filters(request: list[Any], payload: Any) -> list[str]:
    """Names of the filters that were sent but are missing from Google's copy of the request."""
    sent = value_at(request, *SENT_FILTERS_PATH) or []
    echoed = value_at(payload, *ECHOED_FILTERS_PATH) or []
    dropped = [
        name
        for index, name in HOTEL_FILTER_NAMES.items()
        if _is_set(value_at(sent, HOTEL_PART, index))
        and not _same(value_at(sent, HOTEL_PART, index), value_at(echoed, HOTEL_PART, index))
    ]
    dropped += [
        name
        for index, name in BLOCK_FILTER_NAMES.items()
        if _is_set(value_at(sent, index)) and not _same(value_at(sent, index), value_at(echoed, index))
    ]
    return dropped


def _same(sent: Any, echoed: Any) -> bool:
    return bool(_normalized(sent) == _normalized(echoed))


def _normalized(value: Any) -> Any:
    """Google trims trailing empty items, writes flags as true for 1, and may repeat codes ([1] comes back as [1, 1])."""
    if not isinstance(value, list):
        return value
    items = [_normalized(item) for item in value]
    while items and items[-1] in (None, []):
        items.pop()
    if items and all(isinstance(item, int) for item in items):
        return sorted(set(items))
    return items


def _is_set(value: Any) -> bool:
    return bool(value not in (None, [], ''))
