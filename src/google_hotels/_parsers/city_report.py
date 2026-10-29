"""Reads Google Hotels' city report for a search: what you'll pay by star class, when to visit month by month, and
where to stay by neighbourhood, as the three tabs Google shows next to its hotel list.

The report call (axSywf) takes a block the first search page already carries under key 404340221. Field positions
were read from Lisbon in English and Spanish on 2026-10-16: prices come as local text ("$67", "59 €") and
temperatures in the language's unit (flag 2 Fahrenheit for English, 1 Celsius for Spanish).
"""

from __future__ import annotations

import re
from typing import Any

from .._protocol.page_data import value_at

REQUEST_BLOCK_KEY = '404340221'
MODE_WHERE, MODE_WHEN, MODE_PRICES = 1, 2, 3
# What you'll pay: payload[2][3..6] are 2- to 5-star hotels, each [typical, _, _, low, high, hotel count].
FIRST_CLASS_INDEX, FIRST_CLASS = 3, 2
# When to visit: payload[1][1] holds 12 months starting at the check-in month, whose number (0 = January) is in
# payload[1][2]; each is [[high, low, _, _, _, unit], [crowds], [price level, currency, low, high]].
# payload[1][3] is Google's text about the seasons.
MONTHS_PATH, FIRST_MONTH_PATH, SEASONS_TEXT_PATH = (1, 1), (1, 2), (1, 3)
UNIT_CELSIUS, UNIT_FAHRENHEIT = 1, 2
MONTHS = (
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
)
# Where to stay: payload[0][0] lists neighbourhoods, each [[_, description, _, name, tagline, [[_, score]]], price,
# _, [latitude, longitude], _, id, _, _, [highlights], [[outline]], [_, _, hotels search path]].
NEIGHBOURHOODS_PATH = (0, 0)
GOOGLE_ORIGIN = 'https://www.google.com'
AMOUNT = re.compile(r'\d[\d.,\s  ]*')


def report_request_block(search_payload: Any) -> Any:
    """The block the report call needs, found wherever the first search page puts it."""
    found = _find_key(search_payload, REQUEST_BLOCK_KEY)
    return _as_numbers(found[0]) if isinstance(found, list) and found else None


def report_request(query: str, block: Any, mode: int) -> list[Any]:
    request = [[query, None, None, block, None, None, None, None, None, 0], mode]
    return [*request, []] if mode == MODE_WHERE else request


def parse_prices_by_class(payload: Any) -> list[dict[str, Any]]:
    classes = []
    for offset, row in enumerate((value_at(payload, 2) or [])[FIRST_CLASS_INDEX:]):
        if not isinstance(row, list):
            continue
        classes.append(
            {
                'hotelClass': FIRST_CLASS + offset,
                'typicalNightlyPrice': money_text(value_at(row, 0)),
                'typicalRangeLow': money_text(value_at(row, 3)),
                'typicalRangeHigh': money_text(value_at(row, 4)),
                'hotelsCount': value_at(row, 5),
            }
        )
    return classes


def parse_months(payload: Any) -> tuple[list[dict[str, Any]], str | None]:
    months = []
    first = value_at(payload, *FIRST_MONTH_PATH)
    first = first if isinstance(first, int) else 0
    for index, month in enumerate(value_at(payload, *MONTHS_PATH) or []):
        high, low, unit = value_at(month, 0, 0), value_at(month, 0, 1), value_at(month, 0, 5)
        number = (first + index) % len(MONTHS)
        months.append(
            {
                'monthNumber': number + 1,
                'month': MONTHS[number],
                **_temperatures(high, low, unit),
                'crowdLevel': value_at(month, 1, 0),
                'priceLevel': value_at(month, 2, 0),
                'typicalNightlyPriceLow': money_text(value_at(month, 2, 2)),
                'typicalNightlyPriceHigh': money_text(value_at(month, 2, 3)),
            }
        )
    text = value_at(payload, *SEASONS_TEXT_PATH)
    # January to December, whatever month the stay starts in.
    return sorted(months, key=lambda month: month['monthNumber']), text if isinstance(text, str) else None


def parse_neighbourhoods(payload: Any) -> list[dict[str, Any]]:
    neighbourhoods = []
    for entry in value_at(payload, *NEIGHBOURHOODS_PATH) or []:
        about = value_at(entry, 0)
        if not isinstance(value_at(about, 3), str):
            continue
        search_path = value_at(entry, 10, 2)
        neighbourhoods.append(
            {
                'name': value_at(about, 3),
                'tagline': (value_at(about, 4) or '').strip() or None,
                'description': value_at(about, 1),
                'locationScore': _number(value_at(about, 5, 0, 1)),
                'typicalNightlyPrice': money_text(value_at(entry, 1)),
                'latitude': value_at(entry, 3, 0),
                'longitude': value_at(entry, 3, 1),
                'placeId': value_at(entry, 5),
                'highlights': [place for place in value_at(entry, 8) or [] if isinstance(place, str)],
                'outline': value_at(entry, 9, 0, 0) if isinstance(value_at(entry, 9, 0, 0), list) else None,
                'hotelsSearchUrl': f'{GOOGLE_ORIGIN}{search_path}' if isinstance(search_path, str) else None,
            }
        )
    return neighbourhoods


def money_text(text: Any) -> float | None:
    """59 €, $1,234, 1.234 €, 1 234,50 zł: the amount as a number."""
    match = AMOUNT.search(text) if isinstance(text, str) else None
    if not match:
        return None
    digits = re.sub(r'[\s  ]', '', match.group()).rstrip('.,')
    # The last separator is a decimal point only when one or two digits follow it.
    last = max(digits.rfind('.'), digits.rfind(','))
    if last >= 0 and len(digits) - last - 1 in (1, 2):
        whole, decimals = digits[:last], digits[last + 1 :]
    else:
        whole, decimals = digits, ''
    whole = re.sub(r'[.,]', '', whole)
    return float(f'{whole}.{decimals}') if decimals else float(whole)


def _temperatures(high: Any, low: Any, unit: Any) -> dict[str, float | None]:
    if not isinstance(high, (int, float)) or not isinstance(low, (int, float)):
        return {'highCelsius': None, 'lowCelsius': None, 'highFahrenheit': None, 'lowFahrenheit': None}
    if unit == UNIT_FAHRENHEIT:
        return {'highCelsius': _to_celsius(high), 'lowCelsius': _to_celsius(low), 'highFahrenheit': high, 'lowFahrenheit': low}
    return {'highCelsius': high, 'lowCelsius': low, 'highFahrenheit': _to_fahrenheit(high), 'lowFahrenheit': _to_fahrenheit(low)}


def _to_celsius(fahrenheit: float) -> float:
    return round((fahrenheit - 32) * 5 / 9, 1)


def _to_fahrenheit(celsius: float) -> float:
    return round(celsius * 9 / 5 + 32, 1)


def _number(text: Any) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _find_key(node: Any, key: str) -> Any:
    if isinstance(node, dict):
        if key in node:
            return node[key]
        node = list(node.values())
    if isinstance(node, list):
        for item in node:
            found = _find_key(item, key)
            if found is not None:
                return found
    return None


def _as_numbers(node: Any) -> Any:
    # The search page stores switches as true/false; the report call takes them back as 1/0, as Google's page sends them.
    if isinstance(node, list):
        return [_as_numbers(item) for item in node]
    return 1 if node is True else 0 if node is False else node
