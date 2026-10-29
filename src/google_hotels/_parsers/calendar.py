"""Reads Google's date picker answer: the price of the same stay (nights and guests) for each check-in date."""

from __future__ import annotations

from datetime import date
from typing import Any

from .._protocol.page_data import money_at, value_at

# One entry per check-in date: [1] the nightly price, [8] [check-in, check-out, nights], [15] currency,
# [44] [before taxes, taxes, other fees, total]; checked against the hotel page's price.
NIGHTLY_PATH, DATES_PATH, CURRENCY_INDEX, BREAKDOWN_INDEX = (1, 2), (8,), 15, 44


def parse_price_calendar(payload: Any) -> list[dict[str, Any]]:
    days = [_parse_day(day) for day in value_at(payload, 1) or []]
    priced = sorted((day for day in days if day and day['totalRate'] is not None), key=lambda day: day['checkInDate'])
    cheapest = min((day['totalRate'] for day in priced), default=None)
    for day in priced:
        day['isCheapestDate'] = day['totalRate'] == cheapest
    return priced


def _parse_day(day: Any) -> dict[str, Any] | None:
    check_in, check_out = _date(value_at(day, *DATES_PATH, 0)), _date(value_at(day, *DATES_PATH, 1))
    if not check_in or not check_out:
        return None
    breakdown = value_at(day, BREAKDOWN_INDEX) or []
    before_taxes, taxes, fees = money_at(breakdown, 0), money_at(breakdown, 1), money_at(breakdown, 2)
    return {
        'checkInDate': check_in,
        'checkOutDate': check_out,
        'ratePerNight': money_at(day, *NIGHTLY_PATH),
        'totalRate': money_at(breakdown, 3),
        'totalRateBeforeTaxesAndFees': before_taxes,
        'taxesAndFees': round(taxes + (fees or 0), 2) if taxes is not None else None,
        'currency': value_at(day, CURRENCY_INDEX),
    }


def _date(parts: Any) -> str | None:
    if not (isinstance(parts, list) and len(parts) >= 3 and all(isinstance(part, int) for part in parts[:3])):
        return None
    return date(*parts[:3]).isoformat()
