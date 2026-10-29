"""Safe getters for the nested JSON lists Google answers with, and the error for an answer in an unexpected shape."""

from __future__ import annotations

from typing import Any


def money_at(container: Any, *path: int | str) -> float | None:
    """Read a price; Google stores them as long floats such as 83.51878."""
    amount = value_at(container, *path)
    return round(amount, 2) if isinstance(amount, (int, float)) and not isinstance(amount, bool) else None


def value_at(container: Any, *path: int | str) -> Any:
    """Follow `path` through nested lists and dicts; Google omits trailing values, so a missing step returns None."""
    current = container
    for step in path:
        try:
            current = current[step]
        except (IndexError, KeyError, TypeError):
            return None
    return current
