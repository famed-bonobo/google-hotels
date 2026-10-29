"""The stay (dates, guests, currency) and the search filters a caller asks for, validated before any call is sent.

Every filter matches one control of Google Hotels' own filter panel. Hotel filters and vacation-rental filters live in
different parts of Google's request, so mixing them is refused instead of being silently ignored by Google.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from ._protocol import constants
from .errors import InvalidOptionError

PropertyMode = Literal['hotels_and_rentals', 'hotels', 'vacation_rentals']
SortBy = Literal['relevance', 'lowest_price', 'highest_rating', 'most_reviewed']
CURRENCY_PATTERN = re.compile(r'^[A-Z]{3}$')
MAX_ROOMS_FILTER = 20
HOTEL_ONLY_FILTERS = ('hotel_classes', 'amenities', 'hotel_types', 'eco_certified_only')
RENTAL_ONLY_FILTERS = ('rental_types', 'rental_amenities', 'min_bedrooms', 'min_bathrooms')


@dataclass(frozen=True)
class Stay:
    """The dates and guests every price refers to."""

    check_in: date
    check_out: date
    adults: int = constants.DEFAULT_ADULTS
    children_ages: tuple[int, ...] = ()
    currency: str = constants.DEFAULT_CURRENCY

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days


@dataclass(frozen=True)
class SearchFilters:
    property_mode: PropertyMode = 'hotels_and_rentals'
    sort_by: SortBy = 'relevance'
    min_price: int | None = None
    max_price: int | None = None
    min_rating: float | None = None
    hotel_classes: tuple[int, ...] = ()
    amenities: tuple[str, ...] = ()
    hotel_types: tuple[str, ...] = ()
    free_cancellation_only: bool = False
    special_offers_only: bool = False
    eco_certified_only: bool = False
    rental_types: tuple[str, ...] = ()
    rental_amenities: tuple[str, ...] = ()
    min_bedrooms: int | None = None
    min_bathrooms: int | None = None

    @property
    def is_rentals_search(self) -> bool:
        return self.property_mode == 'vacation_rentals'

    def __post_init__(self) -> None:
        _choice('property_mode', self.property_mode, ('hotels_and_rentals', 'hotels', 'vacation_rentals'))
        _choice('sort_by', self.sort_by, tuple(constants.SORT_CODES))
        _amount('min_price', self.min_price)
        _amount('max_price', self.max_price)
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise InvalidOptionError(f'min_price ({self.min_price}) is above max_price ({self.max_price})')
        if self.min_rating is not None:
            _choice('min_rating', float(self.min_rating), tuple(constants.MIN_RATING_CODES))
        _members('hotel_classes', self.hotel_classes, constants.HOTEL_CLASSES)
        _members('amenities', self.amenities, tuple(constants.HOTEL_AMENITY_CODES))
        _members('hotel_types', self.hotel_types, tuple(constants.HOTEL_TYPE_CODES))
        _members('rental_types', self.rental_types, tuple(constants.RENTAL_TYPE_CODES))
        _members('rental_amenities', self.rental_amenities, tuple(constants.RENTAL_AMENITY_CODES))
        _room_count('min_bedrooms', self.min_bedrooms)
        _room_count('min_bathrooms', self.min_bathrooms)
        self._check_mode_fits()

    def _check_mode_fits(self) -> None:
        wrong = HOTEL_ONLY_FILTERS if self.is_rentals_search else RENTAL_ONLY_FILTERS
        used = [name for name in wrong if getattr(self, name)]
        if used and self.is_rentals_search:
            raise InvalidOptionError(
                f'{used} apply to hotels; vacation_rentals searches take rental_types, '
                'rental_amenities, min_bedrooms and min_bathrooms'
            )
        if used:
            raise InvalidOptionError(f'{used} need property_mode="vacation_rentals"')


def make_stay(
    check_in: date | str | None,
    check_out: date | str | None,
    nights: int | None,
    adults: int,
    children_ages: Iterable[int],
    currency: str,
    today: date,
) -> Stay:
    """A validated stay; without dates it starts 14 days from today, as Google's own page does, for one night."""
    start = _date('check_in', check_in) or today + timedelta(days=constants.DEFAULT_DAYS_UNTIL_CHECK_IN)
    end = _date('check_out', check_out)
    if end is not None and nights is not None:
        raise InvalidOptionError('Give check_out or nights, not both')
    if end is None:
        _whole_number('nights', nights if nights is not None else constants.DEFAULT_NIGHTS, 1, constants.MAX_NIGHTS)
        end = start + timedelta(days=nights or constants.DEFAULT_NIGHTS)
    if start < today:
        raise InvalidOptionError(f'check_in is in the past: {start.isoformat()}')
    if start > today + timedelta(days=constants.MAX_DAYS_UNTIL_CHECK_IN):
        raise InvalidOptionError(f'check_in is more than {constants.MAX_DAYS_UNTIL_CHECK_IN} days ahead: {start.isoformat()}')
    if end <= start:
        raise InvalidOptionError(f'check_out ({end.isoformat()}) must be after check_in ({start.isoformat()})')
    _whole_number('adults', adults, 1, constants.MAX_ADULTS)
    ages = tuple(children_ages)
    for age in ages:
        _whole_number('children_ages', age, 0, constants.MAX_CHILD_AGE)
    code = currency.upper() if isinstance(currency, str) else currency
    if not isinstance(code, str) or not CURRENCY_PATTERN.match(code):
        raise InvalidOptionError(f'currency must be a three-letter code such as "EUR", got {currency!r}')
    return Stay(start, end, adults, ages, code)


def _date(name: str, value: date | str | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise InvalidOptionError(f'{name} must be a date or a text like "2026-12-24", got {value!r}') from error


def _whole_number(name: str, value: object, minimum: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise InvalidOptionError(f'{name} must be a whole number from {minimum} to {maximum}, got {value!r}')


def _choice(name: str, value: object, options: tuple[object, ...]) -> None:
    if value not in options:
        raise InvalidOptionError(f'{name} must be one of {list(options)}, got {value!r}')


def _members(name: str, values: tuple[object, ...], options: tuple[object, ...]) -> None:
    if isinstance(values, str):
        raise InvalidOptionError(f'{name} must be a list such as [{options[0]!r}], got the text {values!r}')
    unknown = [value for value in values if value not in options]
    if unknown:
        raise InvalidOptionError(f'{name} has unknown values {unknown}; the choices are {list(options)}')


def _amount(name: str, value: int | None) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise InvalidOptionError(f'{name} must be a whole amount in the chosen currency, got {value!r}')


def _room_count(name: str, value: int | None) -> None:
    if value is not None:
        _whole_number(name, value, 1, MAX_ROOMS_FILTER)
