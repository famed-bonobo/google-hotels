"""Turns Google's localized time and duration labels ("4:00 م", "오후 3:00", "1 hr 21 min", "8 د") into numbers.

Google sends these only as display text in the page language, so the markers below cover the languages Google
Hotels offers; a label that matches none of them gives None rather than a guess.
"""

from __future__ import annotations

import re

TIME_PATTERN = re.compile(r'(\d{1,2})\s*[:.h]\s*(\d{2})')
NUMBER_PATTERN = re.compile(r'\d+')
# Afternoon and morning markers as Google writes them: English, Spanish, Portuguese, Arabic, Korean,
# Japanese, Chinese, Vietnamese, Thai, Hindi, Indonesian and Filipino pages.
AFTERNOON_MARKERS = ('pm', 'p.m.', 'p. m.', 'م', '오후', '午後', '下午', 'ch', 'หลังเที่ยง', 'अपराह्न')
MORNING_MARKERS = ('am', 'a.m.', 'a. m.', 'ص', '오전', '午前', '上午', 'sa', 'ก่อนเที่ยง', 'पूर्वाह्न')
# Units that mark the first number of a duration as hours.
HOUR_UNITS = (
    'hr',
    'hour',
    'h ',
    'std',
    'heure',
    'hora',
    'ora',
    'uur',
    'ساعة',
    'ساعت',
    '시간',
    '時間',
    '小时',
    '小時',
    'giờ',
    'ชั่วโมง',
    'घंटे',
    'jam',
    'saat',
    'час',
)
MINUTES_PER_HOUR = 60
NOON = 12


def to_24_hour_time(label: str | None) -> str | None:
    """ "4:00 PM" -> "16:00"; a label already in 24-hour form keeps its value."""
    if not label:
        return None
    match = TIME_PATTERN.search(label)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    lowered = label.lower().replace(' ', ' ').replace('\xa0', ' ')
    if _has_marker(lowered, AFTERNOON_MARKERS) and hour < NOON:
        hour += NOON
    elif _has_marker(lowered, MORNING_MARKERS) and hour == NOON:
        hour = 0
    return f'{hour:02d}:{minute:02d}' if hour < 24 and minute < MINUTES_PER_HOUR else None


def to_minutes(label: str | None) -> int | None:
    """ "1 hr 21 min" -> 81, "8 د" -> 8, "2 hr" -> 120."""
    if not label:
        return None
    numbers = [int(number) for number in NUMBER_PATTERN.findall(label)]
    if not numbers:
        return None
    if len(numbers) >= 2:
        return numbers[0] * MINUTES_PER_HOUR + numbers[1]
    lowered = f'{label.lower()} '
    return numbers[0] * MINUTES_PER_HOUR if any(unit in lowered for unit in HOUR_UNITS) else numbers[0]


def _has_marker(text: str, markers: tuple[str, ...]) -> bool:
    # Latin markers must stand alone ("pm", not the "pm" inside another word); script markers can touch digits.
    for marker in markers:
        if marker.isascii():
            if re.search(rf'(?<![a-z]){re.escape(marker)}(?![a-z])', text):
                return True
        elif marker in text:
            return True
    return False
