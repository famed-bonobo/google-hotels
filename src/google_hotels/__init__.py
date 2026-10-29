"""Google Hotels data in Python: search results, every booking site's offer, price calendars, reviews and photos.

from google_hotels import GoogleHotels

with GoogleHotels(currency="EUR") as hotels:
    for hotel in hotels.search("hotels in Lisbon", check_in="2026-12-04", nights=2, min_rating=4.5):
        print(hotel["name"], hotel["ratePerNight"])
"""

from .client import AsyncGoogleHotels, GoogleHotels
from .errors import (
    FilterNotAppliedError,
    GoogleBlockedError,
    GoogleHotelsError,
    HotelNotFoundError,
    InvalidOptionError,
    InvalidRequestError,
    PageFormatError,
)

__version__ = '0.1.0'
__all__ = [
    'AsyncGoogleHotels',
    'FilterNotAppliedError',
    'GoogleBlockedError',
    'GoogleHotels',
    'GoogleHotelsError',
    'HotelNotFoundError',
    'InvalidOptionError',
    'InvalidRequestError',
    'PageFormatError',
    '__version__',
]
