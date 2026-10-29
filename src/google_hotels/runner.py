"""Drives a plan to its result: sends each call it names through a transport and hands the answers back to it.

A batch of calls goes out together in both: on a few threads in the sync runner and as tasks in the async one, limited by
the transport's concurrency.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

from .errors import GoogleHotelsError
from .plans import Call, Plan
from .transport import AsyncTransport, SyncTransport

T = TypeVar('T')


def run_sync(plan: Plan[T], transport: SyncTransport) -> T:
    reply: Any = None
    failure: GoogleHotelsError | None = None
    while True:
        try:
            step = plan.throw(failure) if failure else plan.send(reply)
        except StopIteration as finished:
            result: T = finished.value
            return result
        failure = None
        if isinstance(step, Call):
            try:
                reply = transport.call(step.rpc_id, step.request)
            except GoogleHotelsError as error:
                failure = error
        else:
            with ThreadPoolExecutor(max_workers=transport.max_concurrency) as pool:
                reply = list(pool.map(lambda call: _outcome_sync(transport, call), step))


async def run_async(plan: Plan[T], transport: AsyncTransport) -> T:
    reply: Any = None
    failure: GoogleHotelsError | None = None
    while True:
        try:
            step = plan.throw(failure) if failure else plan.send(reply)
        except StopIteration as finished:
            result: T = finished.value
            return result
        failure = None
        if isinstance(step, Call):
            try:
                reply = await transport.call(step.rpc_id, step.request)
            except GoogleHotelsError as error:
                failure = error
        else:
            reply = await asyncio.gather(*(_outcome_async(transport, call) for call in step))


def _outcome_sync(transport: SyncTransport, call: Call) -> Any:
    try:
        return transport.call(call.rpc_id, call.request)
    except GoogleHotelsError as error:
        return error


async def _outcome_async(transport: AsyncTransport, call: Call) -> Any:
    try:
        return await transport.call(call.rpc_id, call.request)
    except GoogleHotelsError as error:
        return error
