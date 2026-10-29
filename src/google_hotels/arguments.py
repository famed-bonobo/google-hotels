"""The keyword arguments the public methods share (the stay and the search filters), turned into validated options.

Declaring them once as TypedDicts keeps the sync and the async client's signatures identical and gives editors
completion for every argument.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from typing import Any, TypedDict

from typing_extensions import Unpack

from .errors import InvalidOptionError
from .hotel_reference import HotelReference, InvalidHotelReferenceError, parse_hotel_reference
from .options import PropertyMode, SearchFilters, SortBy, Stay, make_stay

Hotel = dict[str, Any]
# A hotel as returned by search() or hotel(), its Google Hotels link, its property token, or its name.
HotelLike = Mapping[str, Any] | str


class StayArgs(TypedDict, total=False):
    check_in: date | str
    check_out: date | str
    nights: int
    adults: int
    children_ages: Iterable[int]


class FilterArgs(TypedDict, total=False):
    property_mode: PropertyMode
    sort_by: SortBy
    min_price: int
    max_price: int
    min_rating: float
    hotel_classes: Iterable[int]
    amenities: Iterable[str]
    hotel_types: Iterable[str]
    free_cancellation_only: bool
    special_offers_only: bool
    eco_certified_only: bool
    rental_types: Iterable[str]
    rental_amenities: Iterable[str]
    min_bedrooms: int
    min_bathrooms: int


class SearchArgs(StayArgs, FilterArgs, total=False):
    """A search takes the stay and the filters side by side: search("hotels in Lisbon", nights=2, min_rating=4.5)."""


LIST_FILTERS = ('hotel_classes', 'amenities', 'hotel_types', 'rental_types', 'rental_amenities')


def split_search_args(arguments: SearchArgs) -> tuple[StayArgs, FilterArgs]:
    stay = {name: value for name, value in arguments.items() if name in StayArgs.__annotations__}
    filters = {name: value for name, value in arguments.items() if name not in StayArgs.__annotations__}
    return stay, filters  # type: ignore[return-value]


def stay_of(currency: str, **arguments: Unpack[StayArgs]) -> Stay:
    return make_stay(
        arguments.get('check_in'),
        arguments.get('check_out'),
        arguments.get('nights'),
        arguments.get('adults', 2),
        arguments.get('children_ages', ()),
        currency,
        today=datetime.now(UTC).date(),
    )


def filters_of(**arguments: Unpack[FilterArgs]) -> SearchFilters:
    values: dict[str, Any] = dict(arguments)
    for name in LIST_FILTERS:
        if name in values and not isinstance(values[name], str):
            values[name] = tuple(values[name])
    try:
        return SearchFilters(**values)
    except TypeError as error:
        raise InvalidOptionError(f'Unknown search filter: {error}') from error


def reference_of(hotel: HotelLike) -> HotelReference:
    if isinstance(hotel, Mapping):
        token = hotel.get('propertyToken')
        if not isinstance(token, str):
            raise InvalidOptionError('A hotel given as a dict needs its "propertyToken", as search() returns it')
        return HotelReference(token, token, hotel.get('name'))
    if not isinstance(hotel, str):
        raise InvalidOptionError(f'hotel must be a hotel from search(), a Google Hotels link, a token or a name, got {hotel!r}')
    try:
        return parse_hotel_reference(hotel)
    except InvalidHotelReferenceError as error:
        raise InvalidOptionError(str(error)) from error


def name_of(hotel: HotelLike) -> str:
    """The hotel's name when known; it tells the property's own photos apart from visitors' photos."""
    if isinstance(hotel, Mapping):
        return str(hotel.get('name') or '')
    reference = reference_of(hotel)
    return reference.name or ''


def check_count(name: str, value: object, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise InvalidOptionError(f'{name} must be a whole number from {minimum} to {maximum}, got {value!r}')
    return value


def check_choice(name: str, value: object, choices: Iterable[str]) -> str:
    options = list(choices)
    if value not in options:
        raise InvalidOptionError(f'{name} must be one of {options}, got {value!r}')
    return str(value)
