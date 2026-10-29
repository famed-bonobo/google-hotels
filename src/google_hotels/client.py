"""The public clients: GoogleHotels for plain code and notebooks, AsyncGoogleHotels for asyncio code.

Both take the same arguments and return the same records; the async one also fetches many hotels' offers at once.
Records use the same field names as the hosted Google Hotels Scraper on Apify, so code written against one works
with the other.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Self

from typing_extensions import Unpack

from . import plans
from ._protocol import constants
from .arguments import (
    Hotel,
    HotelLike,
    SearchArgs,
    StayArgs,
    check_choice,
    check_count,
    filters_of,
    name_of,
    reference_of,
    split_search_args,
    stay_of,
)
from .runner import run_async, run_sync
from .transport import AsyncTransport, SyncTransport

MAX_RESULTS_LIMIT = 1000
MAX_REVIEWS_LIMIT = 10_000
MAX_PHOTOS_LIMIT = 500
# Five calls at once kept every answer coming from one home IP in testing; more can trip Google's rate limit.
DEFAULT_CONCURRENCY = 5
MAX_CONCURRENCY = 50


class _Planner:
    """Turns a public call's arguments into the plan that answers it; shared by both clients."""

    def __init__(self, language: str, country: str, currency: str) -> None:
        self.locale = plans.Locale(language.lower(), country.lower())
        self.currency = currency

    def search(self, query: str, max_results: int, with_offers: bool, arguments: SearchArgs) -> plans.Plan[list[Hotel]]:
        check_count('max_results', max_results, 1, MAX_RESULTS_LIMIT)
        stay, filters = split_search_args(arguments)
        return plans.search(query, stay_of(self.currency, **stay), filters_of(**filters), self.locale, max_results, with_offers)

    def hotel(self, hotel: HotelLike, stay: StayArgs) -> plans.Plan[Hotel]:
        return plans.hotel(reference_of(hotel), stay_of(self.currency, **stay), filters_of(), self.locale)

    def price_calendar(self, hotel: HotelLike, days: int, stay: StayArgs) -> plans.Plan[list[dict[str, Any]]]:
        check_count('days', days, 1, constants.MAX_CALENDAR_DAYS)
        chosen = stay_of(self.currency, **stay)
        return plans.for_hotel(reference_of(hotel), chosen, lambda token: plans.price_calendar(token, chosen, days))

    def reviews(self, hotel: HotelLike, limit: int, sort: str, source: str, query: str) -> plans.Plan[list[dict[str, Any]]]:
        check_count('limit', limit, 1, MAX_REVIEWS_LIMIT)
        check_choice('sort', sort, constants.REVIEW_SORT_CODES)
        check_choice('source', source, constants.REVIEW_SOURCES)
        today = datetime.now(UTC).date()
        return plans.for_hotel(
            reference_of(hotel),
            stay_of(self.currency),
            lambda token: plans.reviews(token, limit, sort, source, query.strip(), today),
        )

    def photos(self, hotel: HotelLike, limit: int) -> plans.Plan[list[dict[str, Any]]]:
        check_count('limit', limit, 1, MAX_PHOTOS_LIMIT)
        name = name_of(hotel)
        return plans.for_hotel(reference_of(hotel), stay_of(self.currency), lambda token: plans.photos(token, name, limit))

    def city_report(self, query: str, stay: StayArgs) -> plans.Plan[dict[str, Any] | None]:
        return plans.city_report(query, stay_of(self.currency, **stay), filters_of())


class GoogleHotels:
    """Google Hotels data: hotels of a search, a hotel's offers from every booking site, its price calendar, reviews,
    photos, and the city report.

    Prices are in `currency`; `language` and `country` are Google's hl and gl codes. `proxy` is an http(s) or socks
    proxy URL, for when you make many calls from one IP. `max_concurrency` caps the calls sent at once, such as the
    offers of a page of hotels.
    """

    def __init__(
        self,
        *,
        language: str = constants.DEFAULT_LANGUAGE,
        country: str = constants.DEFAULT_COUNTRY,
        currency: str = constants.DEFAULT_CURRENCY,
        proxy: str | None = None,
        max_concurrency: int = DEFAULT_CONCURRENCY,
    ) -> None:
        self._planner = _Planner(language, country, stay_of(currency).currency)
        concurrency = check_count('max_concurrency', max_concurrency, 1, MAX_CONCURRENCY)
        self._transport = SyncTransport(self._planner.locale.language, self._planner.locale.country, proxy, concurrency)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exception: object) -> None:
        self.close()

    def close(self) -> None:
        self._transport.close()

    def search(
        self,
        query: str,
        *,
        max_results: int = constants.DEFAULT_MAX_RESULTS,
        with_offers: bool = False,
        **arguments: Unpack[SearchArgs],
    ) -> list[Hotel]:
        """Hotels for a search such as "hotels in Lisbon", in Google's order; `with_offers` adds every booking site's offer."""
        return run_sync(self._planner.search(query, max_results, with_offers, arguments), self._transport)

    def hotel(self, hotel: HotelLike, **stay: Unpack[StayArgs]) -> Hotel:
        """One hotel's full page: details, amenities by category, and every booking site's offer with its rooms."""
        return run_sync(self._planner.hotel(hotel, stay), self._transport)

    def price_calendar(self, hotel: HotelLike, *, days: int = 60, **stay: Unpack[StayArgs]) -> list[dict[str, Any]]:
        """The price of the same stay for each check-in day, from check_in on, with the cheapest dates marked."""
        return run_sync(self._planner.price_calendar(hotel, days, stay), self._transport)

    def reviews(
        self, hotel: HotelLike, *, limit: int = 100, sort: str = 'most_helpful', source: str = 'all', query: str = ''
    ) -> list[dict[str, Any]]:
        """Guest reviews; `source="google"` keeps Google's own, `query` keeps those that mention a word."""
        return run_sync(self._planner.reviews(hotel, limit, sort, source, query), self._transport)

    def photos(self, hotel: HotelLike, *, limit: int = 50) -> list[dict[str, Any]]:
        """The property's and booking sites' photos at full size, by category; visitors' photos are left out."""
        return run_sync(self._planner.photos(hotel, limit), self._transport)

    def city_report(self, query: str, **stay: Unpack[StayArgs]) -> dict[str, Any] | None:
        """Prices by star class, the best months to visit, and neighbourhoods; None when Google shows no report."""
        return run_sync(self._planner.city_report(query, stay), self._transport)


class AsyncGoogleHotels:
    """The asyncio version of GoogleHotels, with the same methods; `max_concurrency` caps the calls in flight."""

    def __init__(
        self,
        *,
        language: str = constants.DEFAULT_LANGUAGE,
        country: str = constants.DEFAULT_COUNTRY,
        currency: str = constants.DEFAULT_CURRENCY,
        proxy: str | None = None,
        max_concurrency: int = DEFAULT_CONCURRENCY,
    ) -> None:
        self._planner = _Planner(language, country, stay_of(currency).currency)
        concurrency = check_count('max_concurrency', max_concurrency, 1, MAX_CONCURRENCY)
        self._transport = AsyncTransport(self._planner.locale.language, self._planner.locale.country, proxy, concurrency)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exception: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def search(
        self,
        query: str,
        *,
        max_results: int = constants.DEFAULT_MAX_RESULTS,
        with_offers: bool = False,
        **arguments: Unpack[SearchArgs],
    ) -> list[Hotel]:
        return await run_async(self._planner.search(query, max_results, with_offers, arguments), self._transport)

    async def hotel(self, hotel: HotelLike, **stay: Unpack[StayArgs]) -> Hotel:
        return await run_async(self._planner.hotel(hotel, stay), self._transport)

    async def price_calendar(self, hotel: HotelLike, *, days: int = 60, **stay: Unpack[StayArgs]) -> list[dict[str, Any]]:
        return await run_async(self._planner.price_calendar(hotel, days, stay), self._transport)

    async def reviews(
        self, hotel: HotelLike, *, limit: int = 100, sort: str = 'most_helpful', source: str = 'all', query: str = ''
    ) -> list[dict[str, Any]]:
        return await run_async(self._planner.reviews(hotel, limit, sort, source, query), self._transport)

    async def photos(self, hotel: HotelLike, *, limit: int = 50) -> list[dict[str, Any]]:
        return await run_async(self._planner.photos(hotel, limit), self._transport)

    async def city_report(self, query: str, **stay: Unpack[StayArgs]) -> dict[str, Any] | None:
        return await run_async(self._planner.city_report(query, stay), self._transport)
