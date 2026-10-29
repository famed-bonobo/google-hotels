"""Minimal protocol-buffer encoder for the opaque `ts` and `qs` parameters of Google Hotels URLs.

Only the two wire types those parameters use are supported: varints and length-delimited bytes.
"""

from __future__ import annotations

import base64

VARINT_WIRE_TYPE = 0
LENGTH_DELIMITED_WIRE_TYPE = 2


def encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError(f'Protobuf varints must be non-negative, got {value}')
    encoded = bytearray()
    while True:
        low_bits = value & 0x7F
        value >>= 7
        encoded.append(low_bits | (0x80 if value else 0))
        if not value:
            return bytes(encoded)


def encode_field(field_number: int, value: int | str | bytes) -> bytes:
    if isinstance(value, int):
        return encode_varint(field_number << 3 | VARINT_WIRE_TYPE) + encode_varint(value)
    payload = value.encode() if isinstance(value, str) else value
    key = encode_varint(field_number << 3 | LENGTH_DELIMITED_WIRE_TYPE)
    return key + encode_varint(len(payload)) + payload


def to_url_base64(message: bytes) -> str:
    """Encode a message the way Google writes it in URLs: URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(message).decode().rstrip('=')
