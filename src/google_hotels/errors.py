"""Every error this library raises; all of them derive from GoogleHotelsError, so one except clause can catch them all."""

from __future__ import annotations


class GoogleHotelsError(Exception):
    """Base class of this library's errors."""


class InvalidOptionError(GoogleHotelsError, ValueError):
    """An argument cannot be used; the message names the argument and the value."""


class GoogleBlockedError(GoogleHotelsError):
    """Every attempt at a call was blocked, rate-limited or failed. Wait, slow down, or use a proxy."""


class InvalidRequestError(GoogleHotelsError, ValueError):
    """Google refused the call as invalid, such as dates beyond what it prices; repeating it cannot help."""


class PageFormatError(GoogleHotelsError):
    """Google answered without the data it normally sends; it may be a block or a new format."""


class FilterNotAppliedError(GoogleHotelsError):
    """Google kept answering without one of the requested filters, so its hotels would not match them."""


class HotelNotFoundError(GoogleHotelsError):
    """No Google Hotels page matches the hotel that was named."""
