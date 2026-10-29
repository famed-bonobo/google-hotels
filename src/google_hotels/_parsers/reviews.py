"""Turns a page of Google Hotels reviews into review records, without the reviewer's identity, and the next page token.

Codes were matched against the labels of the hotels' review pages on 2026-10-16: "Vacation ❘ Family" is [6, 1],
"Business ❘ Solo" [2, 3], "Vacation ❘ Couple" [6, 5]; ratings by category were checked against review cards.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .._protocol.page_data import value_at

TRIP_PURPOSES = {2: 'business', 6: 'vacation'}
TRAVEL_GROUPS = {1: 'family', 3: 'solo', 4: 'friends', 5: 'couple'}
RATING_CATEGORIES = {1: 'rooms', 4: 'service', 5: 'location'}
# Paths inside one review r: r[0] is the source, r[1] the review itself.
SOURCE_PATH, TEXT_PATH = (0, 0), (1, 3, 0, 0, 1)
WHEN, RATING, LINK, REPLY, TRIP, CATEGORIES, REVIEW_ID, PHOTOS, HIGHLIGHTS, ANSWERS = 1, 2, 4, 5, 6, 7, 8, 14, 15, 16
REVIEWS_PATH, NEXT_PAGE_PATH = (0, 0), (0, 5)
# A hotel's reply opens by greeting the reviewer by name; that line is left out with the reviewer's identity.
GREETING_PATTERN = re.compile(
    r'^(dear|hi|hello|hey|querid[oa]s?|estimad[oa]s?|hola|olá|cher|chère|liebe[r]?|caro|cara)\b.{0,40}$', re.I
)
# Up to this many opening lines can be salutations ("Olá," then "Dear guest,").
MAX_GREETING_LINES = 3
RELATIVE_TIME_PATTERN = re.compile(r'^(a|an|one|\d+)\s+(minute|hour|day|week|month|year)s?\s+ago$', re.I)
EDITED_PREFIX = 'Edited '
# A review in another language reads "(Translated by Google) <translation>\n(Original)\n<original>".
TRANSLATED_PREFIX, ORIGINAL_MARKER = '(Translated by Google)', '\n(Original)\n'
DAYS_PER_UNIT = {'minute': 0, 'hour': 0, 'day': 1, 'week': 7, 'month': 30, 'year': 365}


@dataclass(frozen=True)
class ReviewPage:
    reviews: list[dict[str, Any]]
    next_page_token: str | None


def parse_review_page(payload: Any, today: date) -> ReviewPage:
    reviews = [
        _parse_review(review, today) for review in value_at(payload, *REVIEWS_PATH) or [] if isinstance(value_at(review, 1), list)
    ]
    token = value_at(payload, *NEXT_PAGE_PATH)
    return ReviewPage(reviews, token if isinstance(token, str) and token else None)


def _parse_review(review: list[Any], today: date) -> dict[str, Any]:
    body = value_at(review, 1)
    trip = [code for code in value_at(body, TRIP) or [] if isinstance(code, int)]
    published_ago: str | None = value_at(body, WHEN) if isinstance(value_at(body, WHEN), str) else None
    is_edited = published_ago is not None and published_ago.startswith(EDITED_PREFIX)
    if published_ago is not None and is_edited:
        published_ago = published_ago.removeprefix(EDITED_PREFIX)
    translation, original = _split_translation(_clean_text(value_at(review, *TEXT_PATH)))
    reply = value_at(body, REPLY)
    return {
        'reviewId': value_at(body, REVIEW_ID),
        'source': value_at(review, *SOURCE_PATH),
        'rating': value_at(body, RATING, 0),
        'maxRating': value_at(body, RATING, 1),
        'text': translation,
        'originalText': original,
        'publishedAgo': published_ago,
        'publishedAtEstimate': estimate_date(published_ago, today),
        'isEdited': is_edited,
        'tripPurpose': next((TRIP_PURPOSES[code] for code in trip if code in TRIP_PURPOSES), None),
        'travelGroup': next((TRAVEL_GROUPS[code] for code in trip if code in TRAVEL_GROUPS), None),
        'categoryRatings': {
            RATING_CATEGORIES[code]: value_at(score, 0)
            for code, score in value_at(body, CATEGORIES) or []
            if code in RATING_CATEGORIES
        },
        'highlights': [item for item in value_at(body, HIGHLIGHTS, 1) or [] if isinstance(item, str)],
        'topicAnswers': [
            {'topic': topic, 'answer': _clean_text(answer)}
            for topic, answer in value_at(body, ANSWERS) or []
            if isinstance(topic, str) and isinstance(answer, str)
        ],
        # The reply is [lines, when]: its text and how long ago the hotel answered.
        'hotelReply': _reply(value_at(reply, 0)),
        'hotelReplyAgo': value_at(reply, 1) if isinstance(value_at(reply, 1), str) else None,
        'reviewUrl': value_at(body, LINK) or None,
        'photosCount': len(value_at(body, PHOTOS) or []),
    }


def estimate_date(published_ago: Any, today: date) -> str | None:
    """The day "2 months ago" points to, from today's date; None for wording it cannot read."""
    match = RELATIVE_TIME_PATTERN.match(published_ago.strip()) if isinstance(published_ago, str) else None
    if not match:
        return None
    amount = 1 if match.group(1).lower() in ('a', 'an', 'one') else int(match.group(1))
    return (today - timedelta(days=amount * DAYS_PER_UNIT[match.group(2).lower()])).isoformat()


def _split_translation(text: str | None) -> tuple[str | None, str | None]:
    """The review in the search language and, for a translated review, its original words."""
    if not text or not text.startswith(TRANSLATED_PREFIX) or ORIGINAL_MARKER not in text:
        return text, None
    translation, original = text.removeprefix(TRANSLATED_PREFIX).split(ORIGINAL_MARKER, 1)
    return translation.strip() or None, original.strip() or None


def _reply(parts: Any) -> str | None:
    # Some replies come as one block with line breaks inside, so lines are taken after joining.
    lines = '\n'.join(part for part in parts or [] if isinstance(part, str)).split('\n')
    greetings = 0
    while lines and greetings < MAX_GREETING_LINES and (not lines[0].strip() or GREETING_PATTERN.match(lines[0].strip())):
        greetings += bool(lines[0].strip())
        lines.pop(0)
    return _clean_text('\n'.join(lines))


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = html.unescape(value.replace('<br>', '\n'))
    return re.sub(r'\n{3,}', '\n\n', text).strip() or None
