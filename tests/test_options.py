"""Argument validation: every refusal names the argument and the value, before any call is sent."""

from __future__ import annotations

from datetime import date

import pytest

from google_hotels import InvalidOptionError
from google_hotels.arguments import filters_of, reference_of, split_search_args
from google_hotels.options import SearchFilters, make_stay

TODAY = date(2026, 10, 29)


def test_default_stay_starts_two_weeks_ahead_for_one_night() -> None:
    stay = make_stay(None, None, None, 2, (), 'usd', TODAY)
    assert stay.check_in == date(2026, 11, 12) and stay.nights == 1 and stay.currency == 'USD'


def test_stay_from_text_dates_and_nights() -> None:
    stay = make_stay('2026-12-04', None, 3, 1, [5, 9], 'EUR', TODAY)
    assert stay.check_out == date(2026, 12, 7) and stay.children_ages == (5, 9)


@pytest.mark.parametrize(
    ('arguments', 'message'),
    [
        ({'check_in': '2026-10-01'}, 'in the past'),
        ({'check_in': '04/12/2026'}, 'check_in must be a date'),
        ({'check_in': '2026-12-04', 'check_out': '2026-12-04'}, 'must be after'),
        ({'check_out': '2026-12-06', 'nights': 2}, 'not both'),
        ({'nights': 0}, 'nights must be'),
        ({'adults': 0}, 'adults must be'),
        ({'children_ages': [18]}, 'children_ages must be'),
        ({'currency': 'euro'}, 'currency must be'),
    ],
)
def test_bad_stays_are_refused(arguments: dict, message: str) -> None:
    values = {
        'check_in': None,
        'check_out': None,
        'nights': None,
        'adults': 2,
        'children_ages': (),
        'currency': 'USD',
        **arguments,
    }
    with pytest.raises(InvalidOptionError, match=message):
        make_stay(
            values['check_in'],
            values['check_out'],
            values['nights'],
            values['adults'],
            values['children_ages'],
            values['currency'],
            TODAY,
        )


@pytest.mark.parametrize(
    ('arguments', 'message'),
    [
        ({'sort_by': 'cheapest'}, 'sort_by must be one of'),
        ({'min_rating': 4.2}, 'min_rating must be one of'),
        ({'amenities': ['jacuzzi']}, "unknown values \\['jacuzzi'\\]"),
        ({'amenities': 'pool'}, 'must be a list'),
        ({'min_price': 300, 'max_price': 100}, 'above max_price'),
        ({'rental_types': ['villas']}, 'need property_mode="vacation_rentals"'),
        ({'property_mode': 'vacation_rentals', 'hotel_classes': [5]}, 'apply to hotels'),
    ],
)
def test_bad_filters_are_refused(arguments: dict, message: str) -> None:
    with pytest.raises(InvalidOptionError, match=message):
        filters_of(**arguments)


def test_unknown_filter_names_are_refused() -> None:
    with pytest.raises(InvalidOptionError, match='Unknown search filter'):
        filters_of(stars=5)  # type: ignore[call-arg]


def test_integer_ratings_and_iterables_are_accepted() -> None:
    filters = filters_of(min_rating=4, hotel_classes=range(4, 6))
    assert filters == SearchFilters(min_rating=4, hotel_classes=(4, 5))


def test_search_arguments_split_into_stay_and_filters() -> None:
    stay, filters = split_search_args({'nights': 2, 'min_rating': 4.5, 'adults': 1})
    assert stay == {'nights': 2, 'adults': 1} and filters == {'min_rating': 4.5}


def test_hotels_can_be_named_four_ways() -> None:
    token = 'ChcIqZGU6Zmyx7J7GgsvZy8xdGQ1MXBrNBAB'
    assert reference_of({'propertyToken': token, 'name': 'Hotel Arts'}).property_token == token
    assert reference_of(f'https://www.google.com/travel/hotels/entity/{token}/prices?hl=en').property_token == token
    assert reference_of(token).property_token == token
    assert reference_of('Hotel Arts Barcelona').name == 'Hotel Arts Barcelona'
    with pytest.raises(InvalidOptionError, match='propertyToken'):
        reference_of({'name': 'no token'})
    with pytest.raises(InvalidOptionError, match='not a Google Hotels hotel link'):
        reference_of('https://www.booking.com/hotel/pt/x.html')
