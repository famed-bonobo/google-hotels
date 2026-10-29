"""Encodes one call in Google's batchexecute envelope and reads the call's JSON payload back from the framed answer."""

from __future__ import annotations

import json
import re
from typing import Any

from ..errors import InvalidRequestError

# The answer starts with this anti-JSON-hijacking line, then repeats "<length>\n<json array>".
ANSWER_PREFIX = ")]}'"
CHUNK_LENGTH_LINE = re.compile(r'\s*(\d+)\n')
DATA_ROW_MARKER = 'wrb.fr'
CALL_INDEX = '1'
COMPACT = (',', ':')
# Google's status code for a request it cannot serve as asked, such as dates beyond what it prices.
INVALID_ARGUMENT = 3


def encode_call(rpc_id: str, request: list[Any]) -> str:
    """The `f.req` form field for a single call; Google expects the request itself as a JSON string."""
    return json.dumps([[[rpc_id, json.dumps(request, separators=COMPACT), None, CALL_INDEX]]], separators=COMPACT)


def read_payload(answer: str, rpc_id: str) -> tuple[Any, str | None]:
    """Return the call's payload and None, or None and a description of why the answer holds no data."""
    if not answer.startswith(ANSWER_PREFIX):
        return None, f'answer does not start with the batchexecute prefix: {answer[:80]!r}'
    decoder = json.JSONDecoder()
    position = answer.index('\n') + 1
    while match := CHUNK_LENGTH_LINE.match(answer, position):
        try:
            chunk, position = decoder.raw_decode(answer, match.end())
        except json.JSONDecodeError as error:
            return None, f'answer chunk is not valid JSON: {error}'
        for row in chunk:
            if not (isinstance(row, list) and len(row) > 2 and row[0] == DATA_ROW_MARKER and row[1] == rpc_id):
                continue
            if row[2] is None:
                # Google answers a call it rejects with an empty payload and a status code further in the row.
                if _status_code(row) == INVALID_ARGUMENT:
                    raise InvalidRequestError(f'Google refused the {rpc_id} call as invalid: {json.dumps(row)[:200]}')
                return None, f'Google rejected the {rpc_id} call: {json.dumps(row)[:200]}'
            return json.loads(row[2]), None
    return None, f'answer has no data row for {rpc_id}'


def _status_code(row: list[Any]) -> Any:
    status = row[5] if len(row) > 5 else None
    return status[0] if isinstance(status, list) and status else None
