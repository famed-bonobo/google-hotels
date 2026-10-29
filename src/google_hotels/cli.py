"""The google-hotels command: search, look up a hotel, read its price calendar or reviews, and print JSON or CSV.

google-hotels search "hotels in Lisbon" --check-in 2026-12-04 --nights 2 --min-rating 4.5 --offers --format csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections.abc import Sequence
from typing import Any

from . import __version__
from ._protocol import constants
from .client import GoogleHotels
from .errors import GoogleHotelsError

STAY_OPTIONS = ('check_in', 'check_out', 'nights', 'adults')
FILTER_OPTIONS = ('sort_by', 'min_price', 'max_price', 'min_rating', 'hotel_classes', 'amenities', 'property_mode')


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    # Hotel names and reviews come in every language; a Windows console would otherwise write them in its code page.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        with GoogleHotels(
            language=arguments.language, country=arguments.country, currency=arguments.currency, proxy=arguments.proxy
        ) as hotels:
            records = _run(hotels, arguments)
    except GoogleHotelsError as error:
        print(f'google-hotels: {error}', file=sys.stderr)
        return 1
    _write(records, arguments.format)
    return 0


def _run(hotels: GoogleHotels, arguments: argparse.Namespace) -> list[dict[str, Any]]:
    stay = {name: getattr(arguments, name) for name in STAY_OPTIONS if getattr(arguments, name) is not None}
    if arguments.command == 'search':
        filters = {name: getattr(arguments, name) for name in FILTER_OPTIONS if getattr(arguments, name) is not None}
        return hotels.search(arguments.query, max_results=arguments.max_results, with_offers=arguments.offers, **stay, **filters)
    if arguments.command == 'hotel':
        return [hotels.hotel(arguments.hotel, **stay)]
    if arguments.command == 'calendar':
        return hotels.price_calendar(arguments.hotel, days=arguments.days, **stay)
    return hotels.reviews(
        arguments.hotel, limit=arguments.limit, sort=arguments.sort, source=arguments.source, query=arguments.query
    )


def _write(records: list[dict[str, Any]], output_format: str) -> None:
    if output_format == 'json':
        json.dump(records, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write('\n')
        return
    # CSV keeps one row per record; nested values (offers, rooms, amenities) are written as JSON text.
    columns = list(dict.fromkeys(column for record in records for column in record))
    writer = csv.DictWriter(sys.stdout, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    for record in records:
        writer.writerow(
            {
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                for key, value in record.items()
            }
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='google-hotels',
        description='Google Hotels data: hotels, offers from every booking site, price calendars and reviews.',
    )
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    commands = parser.add_subparsers(dest='command', required=True)
    search = commands.add_parser('search', help='hotels for a search such as "hotels in Lisbon"')
    search.add_argument('query')
    search.add_argument('--max-results', type=int, default=constants.DEFAULT_MAX_RESULTS)
    search.add_argument('--offers', action='store_true', help="add every booking site's offer to each hotel")
    search.add_argument('--sort-by', choices=list(constants.SORT_CODES))
    search.add_argument('--min-price', type=int)
    search.add_argument('--max-price', type=int)
    search.add_argument('--min-rating', type=float, choices=list(constants.MIN_RATING_CODES))
    search.add_argument('--hotel-classes', type=int, nargs='+', choices=constants.HOTEL_CLASSES, metavar='STARS')
    search.add_argument('--amenities', nargs='+', choices=list(constants.HOTEL_AMENITY_CODES), metavar='AMENITY')
    search.add_argument('--property-mode', choices=['hotels_and_rentals', 'hotels', 'vacation_rentals'])
    hotel = commands.add_parser('hotel', help="one hotel's page with every booking site's offer")
    calendar = commands.add_parser('calendar', help='the price of the same stay for each check-in day')
    calendar.add_argument('--days', type=int, default=60)
    reviews = commands.add_parser('reviews', help="a hotel's guest reviews")
    reviews.add_argument('--limit', type=int, default=100)
    reviews.add_argument('--sort', choices=list(constants.REVIEW_SORT_CODES), default='most_helpful')
    reviews.add_argument('--source', choices=list(constants.REVIEW_SOURCES), default='all')
    reviews.add_argument('--query', default='', help='keep only reviews that mention this text')
    for command in (hotel, calendar, reviews):
        command.add_argument('hotel', help='a Google Hotels link, a property token, or the hotel name with its city')
    for command in (search, hotel, calendar, reviews):
        _add_common(command)
    return parser


def _add_common(command: argparse.ArgumentParser) -> None:
    command.add_argument('--check-in', help='YYYY-MM-DD; default 14 days from today')
    command.add_argument('--check-out', help='YYYY-MM-DD')
    command.add_argument('--nights', type=int)
    command.add_argument('--adults', type=int)
    command.add_argument('--currency', default=constants.DEFAULT_CURRENCY)
    command.add_argument('--language', default=constants.DEFAULT_LANGUAGE, help="Google's hl code, such as en or es")
    command.add_argument('--country', default=constants.DEFAULT_COUNTRY, help="Google's gl code, such as us or gb")
    command.add_argument('--proxy', help='http(s) or socks proxy URL')
    command.add_argument('--format', choices=['json', 'csv'], default='json')


if __name__ == '__main__':
    raise SystemExit(main())
