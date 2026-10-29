"""Builds the Google Hotels page link stored with each hotel, including the protobuf-encoded `ts` (stay) parameter."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from ..options import Stay
from . import constants as config
from .protobuf import encode_field, to_url_base64


def build_stay_parameter(stay: Stay) -> str:
    """Encode dates, guests and currency the same way Google's own search page does."""
    guests = b''.join(encode_field(1, encode_field(1, config.ADULT_GUEST_TYPE)) for _ in range(stay.adults))
    guests += encode_field(2, 0)
    stay_dates = (
        encode_field(1, _encode_date(stay.check_in))
        + encode_field(2, _encode_date(stay.check_out))
        + encode_field(3, stay.nights)
    )
    dates = encode_field(2, encode_field(2, stay_dates) + encode_field(6, encode_field(2, 0)))
    currency = encode_field(1, encode_field(7, stay.currency)) + encode_field(3, b'')
    message = encode_field(1, 1) + encode_field(2, guests) + encode_field(3, dates) + encode_field(5, currency)
    return to_url_base64(message)


def build_hotel_url(property_token: str, stay: Stay, language: str, country: str) -> str:
    path = config.HOTEL_URL_TEMPLATE.format(token=property_token)
    parameters = {'hl': language, 'gl': country, 'ts': build_stay_parameter(stay)}
    return f'{path}?{urlencode(parameters)}'


def _encode_date(day: date) -> bytes:
    return encode_field(1, day.year) + encode_field(2, day.month) + encode_field(3, day.day)
