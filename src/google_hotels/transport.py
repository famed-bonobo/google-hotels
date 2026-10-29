"""Sends one Google Travel call over HTTP and retries it when Google rate-limits, blocks or answers without data.

One HTTP client is kept per transport, so Google's cookie survives across calls: without it Google shuffles the
result order on every search page, and its page token is only an offset, so pages repeat some hotels and skip others.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

import httpx

from ._protocol import constants
from ._protocol.batchexecute import encode_call, read_payload
from .errors import GoogleBlockedError

logger = logging.getLogger('google_hotels')
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
BLOCK_PAGE_PATH = '/sorry/'
TIMEOUT = httpx.Timeout(constants.REQUEST_TIMEOUT_SECONDS, read=constants.ATTEMPT_DEADLINE_SECONDS)


def _parameters(rpc_id: str, language: str, country: str) -> dict[str, str]:
    return {'rpcids': rpc_id, 'source-path': constants.RPC_SOURCE_PATH, 'hl': language, 'gl': country, 'rt': 'c'}


def _headers(language: str) -> dict[str, str]:
    return {**constants.REQUEST_HEADERS, 'Accept-Language': f'{language},en;q=0.8'}


def _read(response: httpx.Response, rpc_id: str) -> tuple[Any, str | None]:
    """The call's payload and None, or None and why the answer holds no data."""
    if BLOCK_PAGE_PATH in str(response.url):
        return None, 'Google showed its unusual-traffic page'
    if response.status_code in RETRYABLE_STATUS_CODES:
        return None, f'HTTP {response.status_code}'
    if response.status_code != 200:
        return None, f'unexpected HTTP {response.status_code}'
    return read_payload(response.text, rpc_id)


def _delay(attempt: int) -> float:
    return constants.RETRY_BASE_DELAY_SECONDS * attempt + random.random()


def _give_up(rpc_id: str, problem: str) -> GoogleBlockedError:
    return GoogleBlockedError(
        f'Gave up after {constants.MAX_FETCH_ATTEMPTS} attempts at {rpc_id}: {problem}. '
        'Google may be rate-limiting this IP: wait a few minutes, make fewer calls at once, or pass a proxy.'
    )


class SyncTransport:
    def __init__(self, language: str, country: str, proxy: str | None, max_concurrency: int) -> None:
        self._language, self._country = language, country
        # httpx.Client is safe to share across threads; batches use this many at once.
        self.max_concurrency = max_concurrency
        self._http = httpx.Client(proxy=proxy, headers=_headers(language), timeout=TIMEOUT, follow_redirects=True)

    def close(self) -> None:
        self._http.close()

    def call(self, rpc_id: str, request: list[Any]) -> Any:
        problem: str | None = 'no attempt made'
        for attempt in range(1, constants.MAX_FETCH_ATTEMPTS + 1):
            try:
                response = self._http.post(
                    constants.BATCHEXECUTE_URL,
                    params=_parameters(rpc_id, self._language, self._country),
                    data={'f.req': encode_call(rpc_id, request)},
                )
                payload, problem = _read(response, rpc_id)
            except httpx.HTTPError as error:
                payload, problem = None, f'network error {type(error).__name__}: {error}'
            if problem is None:
                return payload
            if attempt < constants.MAX_FETCH_ATTEMPTS:
                wait = _delay(attempt)
                logger.warning('Attempt %d at %s failed (%s); retrying in %.1fs', attempt, rpc_id, problem, wait)
                time.sleep(wait)
        raise _give_up(rpc_id, problem or 'no answer')


class AsyncTransport:
    def __init__(self, language: str, country: str, proxy: str | None, max_concurrency: int) -> None:
        self._language, self._country = language, country
        self._http = httpx.AsyncClient(proxy=proxy, headers=_headers(language), timeout=TIMEOUT, follow_redirects=True)
        self._slots = asyncio.Semaphore(max_concurrency)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def call(self, rpc_id: str, request: list[Any]) -> Any:
        problem: str | None = 'no attempt made'
        for attempt in range(1, constants.MAX_FETCH_ATTEMPTS + 1):
            async with self._slots:
                payload, problem = await self._attempt(rpc_id, request)
            if problem is None:
                return payload
            if attempt < constants.MAX_FETCH_ATTEMPTS:
                wait = _delay(attempt)
                logger.warning('Attempt %d at %s failed (%s); retrying in %.1fs', attempt, rpc_id, problem, wait)
                await asyncio.sleep(wait)
        raise _give_up(rpc_id, problem or 'no answer')

    async def _attempt(self, rpc_id: str, request: list[Any]) -> tuple[Any, str | None]:
        # The read timeout never fires while a throttled connection trickles bytes, so each attempt has a total deadline.
        try:
            async with asyncio.timeout(constants.ATTEMPT_DEADLINE_SECONDS):
                response = await self._http.post(
                    constants.BATCHEXECUTE_URL,
                    params=_parameters(rpc_id, self._language, self._country),
                    data={'f.req': encode_call(rpc_id, request)},
                )
        except TimeoutError:
            return None, f'no complete answer within {constants.ATTEMPT_DEADLINE_SECONDS}s'
        except httpx.HTTPError as error:
            return None, f'network error {type(error).__name__}: {error}'
        return _read(response, rpc_id)
