"""Plans driven by both runners over a fake transport: paging, filter retries, partial failures and hotel lookup."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

import pytest

from google_hotels import FilterNotAppliedError, GoogleBlockedError, HotelNotFoundError, plans
from google_hotels.hotel_reference import HotelReference
from google_hotels.options import SearchFilters, Stay
from google_hotels.runner import run_async, run_sync

from .builders import nested
from .test_parsers import search_entry, search_payload

STAY = Stay(date(2026, 12, 4), date(2026, 12, 6))
LOCALE = plans.Locale('en', 'us')


class FakeTransport:
    """Answers each call id from a queue of payloads, or from a {property token: payload} map for calls sent together,
    whose order varies; an exception as an answer is raised instead."""

    max_concurrency = 3

    def __init__(self, answers: dict[str, list[Any] | dict[str, Any]]) -> None:
        self.answers = defaultdict(
            list, {rpc_id: answer if isinstance(answer, dict) else list(answer) for rpc_id, answer in answers.items()}
        )
        self.calls: list[tuple[str, list[Any]]] = []

    def call(self, rpc_id: str, request: list[Any]) -> Any:
        self.calls.append((rpc_id, request))
        source = self.answers[rpc_id]
        answer = source[request[3]] if isinstance(source, dict) else source.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class AsyncFakeTransport(FakeTransport):
    async def call(self, rpc_id: str, request: list[Any]) -> Any:  # type: ignore[override]
        return FakeTransport.call(self, rpc_id, request)


def echoing(payload: list, filters_echo: list) -> list:
    payload = list(payload)
    payload.extend([None] * (2 - len(payload)))
    payload[1] = nested({(0, 4): filters_echo})
    payload[1][0][2] = nested({(0, 1, 0, 6): 'Lisbon'})
    return payload


def prices_page(name: str, rate: float) -> list:
    return nested({(0, 1): name, (0, 6, 2, 21): [nested({(0, 0): 'Booking.com', (12, 4, 2): rate})]})


@pytest.mark.parametrize('runner', ['sync', 'async'])
async def test_search_pages_until_enough_hotels_and_adds_offers(runner: str) -> None:
    first = search_payload([search_entry('A', 'TA'), search_entry('B', 'TB')], 'PAGE2')
    second = search_payload([search_entry('B', 'TB'), search_entry('C', 'TC')], 'PAGE3')
    offers = {'TA': prices_page('A', 80.0), 'TB': GoogleBlockedError('blocked'), 'TC': prices_page('C', 95.0)}
    answers = {'AtySUc': [first, second], 'lvkpBc': offers}
    plan = plans.search('hotels in Lisbon', STAY, SearchFilters(), LOCALE, max_results=3, with_offers=True)
    hotels = await _run(runner, plan, answers)
    assert [hotel['name'] for hotel in hotels] == ['A', 'B', 'C']
    assert [hotel['position'] for hotel in hotels] == [1, 2, 3]
    assert hotels[0]['lowestOfferRatePerNight'] == 80.0
    # One hotel's blocked offers leave that hotel without offers instead of failing the search.
    assert hotels[1]['bookingSources'] is None
    assert hotels[2]['bookingSources'][0]['ratePerNight'] == 95.0
    assert hotels[0]['googleHotelsUrl'].startswith('https://www.google.com/travel/hotels/entity/TA?')


def test_search_stops_after_pages_without_new_hotels() -> None:
    repeat = search_payload([search_entry('A', 'TA')], 'MORE')
    transport = FakeTransport({'AtySUc': [repeat, repeat, repeat, repeat]})
    hotels = run_sync(plans.search('q', STAY, SearchFilters(), LOCALE, 10, with_offers=False), transport)  # type: ignore[arg-type]
    assert len(hotels) == 1 and len(transport.calls) == 3


def test_search_asks_again_when_google_drops_a_filter() -> None:
    filters = SearchFilters(hotel_classes=(5,))
    lost = echoing(search_payload([search_entry('Wrong', 'TW')], None), [[None, None, None, None, None, None, 'USD']])
    kept = echoing(search_payload([search_entry('Right', 'TR')], None), [[None, [5], None, None, None, None, 'USD']])
    transport = FakeTransport({'AtySUc': [lost, kept]})
    hotels = run_sync(plans.search('q', STAY, filters, LOCALE, 5, with_offers=False), transport)  # type: ignore[arg-type]
    assert [hotel['name'] for hotel in hotels] == ['Right']


def test_search_gives_up_when_google_keeps_dropping_a_filter() -> None:
    lost = echoing(search_payload([search_entry('Wrong', 'TW')], None), [[None]])
    transport = FakeTransport({'AtySUc': [lost] * 4})
    with pytest.raises(FilterNotAppliedError, match='hotelClasses'):
        run_sync(plans.search('q', STAY, SearchFilters(hotel_classes=(5,)), LOCALE, 5, with_offers=False), transport)  # type: ignore[arg-type]


def test_hotel_by_name_refuses_a_different_first_result() -> None:
    transport = FakeTransport({'AtySUc': [search_payload([search_entry('Hotel Avenida Palace', 'TP')], None)]})
    with pytest.raises(HotelNotFoundError, match='first result was'):
        run_sync(plans.hotel(HotelReference('Ritz Lisbon', None, 'Ritz Lisbon'), STAY, SearchFilters(), LOCALE), transport)  # type: ignore[arg-type]


def test_hotel_by_name_returns_the_page_with_offers() -> None:
    transport = FakeTransport(
        {
            'AtySUc': [search_payload([search_entry('Hotel Avenida Palace', 'TP')], None)],
            'lvkpBc': [prices_page('Avenida Palace', 296.0)],
        }
    )
    found = run_sync(
        plans.hotel(HotelReference('Avenida Palace', None, 'Avenida Palace'), STAY, SearchFilters(), LOCALE), transport
    )  # type: ignore[arg-type]
    assert found['matchedBy'] == 'name' and found['propertyToken'] == 'TP' and found['lowestOfferRatePerNight'] == 296.0


def test_reviews_page_until_the_limit() -> None:
    def review_page(count: int, next_token: str | None) -> list:
        reviews = [[['Google'], nested({(2,): [4, 5], (8,): f'r{number}'})] for number in range(count)]
        return nested({(0, 0): reviews, (0, 5): next_token})

    transport = FakeTransport({'ocp93e': [review_page(200, 'N1'), review_page(200, 'N2')]})
    found = run_sync(plans.reviews('T', 250, 'newest', 'all', '', date(2026, 10, 29)), transport)  # type: ignore[arg-type]
    assert len(found) == 250
    assert [request[3] for _, request in transport.calls] == [200, 50]


def test_a_failed_single_call_raises_from_the_plan() -> None:
    transport = FakeTransport({'yY52ce': [GoogleBlockedError('every attempt failed')]})
    with pytest.raises(GoogleBlockedError):
        run_sync(plans.price_calendar('T', STAY, 30), transport)  # type: ignore[arg-type]


async def _run(runner: str, plan: plans.Plan[Any], answers: dict[str, Any]) -> Any:
    if runner == 'sync':
        return run_sync(plan, FakeTransport(answers))  # type: ignore[arg-type]
    return await run_async(plan, AsyncFakeTransport(answers))  # type: ignore[arg-type]
