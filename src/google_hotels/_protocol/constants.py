"""Google Travel's internal endpoints, call ids and codes, and the limits measured against live answers.

The numeric keys and codes below were mapped by hand against live Google Hotels pages (October 2026).
"""

# Google Travel's internal calls behind the search page and a hotel's prices page. They answer with the same
# JSON the pages embed, 6 to 8 times lighter than downloading the pages.
BATCHEXECUTE_URL = 'https://www.google.com/_/TravelFrontendUi/data/batchexecute'
RPC_SOURCE_PATH = '/travel/search'
SEARCH_RPC_ID = 'AtySUc'
PRICES_RPC_ID = 'lvkpBc'
PRICES_VIEW = 'prices'
CALENDAR_RPC_ID = 'yY52ce'
REVIEWS_RPC_ID = 'ocp93e'
PHOTO_CATEGORIES_RPC_ID = 'pSDzMb'
PHOTOS_RPC_ID = 'VxbZPe'
CITY_REPORT_RPC_ID = 'axSywf'
# 50 photos per call work; the categories call refuses more than 26 cover photos.
PHOTOS_PER_CALL = 50
# 200 reviews per call work; 300 and more are refused.
REVIEWS_PER_CALL = 200
REVIEW_SORT_CODES = {'most_helpful': 1, 'newest': 2, 'highest_rating': 3, 'lowest_rating': 4}
# Google's own reviews have source -1; without a source every site Google shows (Tripadvisor, Trip.com...) is mixed in.
REVIEW_SOURCES = {'all': None, 'google': [-1]}
# Google prices about 300 check-in days ahead (a 400-day request had 301 priced days).
MAX_CALENDAR_DAYS = 400
HOTEL_URL_TEMPLATE = 'https://www.google.com/travel/hotels/entity/{token}'
GOOGLE_ORIGIN = 'https://www.google.com'

REQUEST_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'),
    'Accept': '*/*',
}
REQUEST_TIMEOUT_SECONDS = 45
# A healthy answer arrives in 1-5 s; a throttled connection can trickle bytes without tripping the read timeout,
# so each attempt also gets a total deadline.
ATTEMPT_DEADLINE_SECONDS = 20
MAX_FETCH_ATTEMPTS = 5
RETRY_BASE_DELAY_SECONDS = 2

# Keys of the result objects inside the search answer.
HOTEL_RESULT_KEY = '397419284'
NEXT_PAGE_KEY = '410579159'

# Value Google sends next to the page token when it requests the next page of results.
NEXT_PAGE_VIEW_CODE = 13
# Guest type Google uses for an adult, both in the search call and in the `ts` URL parameter.
ADULT_GUEST_TYPE = 3
CHILD_GUEST_TYPE = 2
# Google sometimes repeats hotels across pages; stop after this many pages in a row without new hotels.
MAX_PAGES_WITHOUT_NEW_HOTELS = 2

# Codes Google uses for how to reach a nearby place, checked against the labels on hotel location pages.
TRANSPORT_MODES = {
    0: 'taxi',
    2: 'walking',
    3: 'public transport',
    8: 'taxi',
}

MAX_DAYS_UNTIL_CHECK_IN = 500
MAX_NIGHTS = 30
DEFAULT_DAYS_UNTIL_CHECK_IN = 14
DEFAULT_NIGHTS = 1
DEFAULT_ADULTS = 2
MAX_ADULTS = 12
MAX_CHILD_AGE = 17
DEFAULT_CURRENCY = 'USD'
DEFAULT_LANGUAGE = 'en'
DEFAULT_COUNTRY = 'us'
DEFAULT_MAX_RESULTS = 20

# Search filters of the AtySUc call, each verified against the returned hotels. Keys are this library's values.
SORT_CODES = {'relevance': None, 'lowest_price': 3, 'highest_rating': 8, 'most_reviewed': 13}
# Minimum guest rating is sent doubled: 4.5+ is 9.
MIN_RATING_CODES = {3.5: 7, 4.0: 8, 4.5: 9}
HOTEL_CLASSES = (2, 3, 4, 5)
HOTEL_AMENITY_CODES = {
    'free_wifi': 35,
    'free_breakfast': 9,
    'restaurant': 8,
    'bar': 15,
    'kid_friendly': 12,
    'pet_friendly': 19,
    'free_parking': 1,
    'parking': 3,
    'ev_charger': 61,
    'room_service': 22,
    'fitness_center': 7,
    'spa': 10,
    'pool': 6,
    'indoor_pool': 4,
    'outdoor_pool': 5,
    'air_conditioned': 40,
    'wheelchair_accessible': 53,
    'beach_access': 11,
    'all_inclusive_available': 52,
}
HOTEL_TYPE_CODES = {
    'beach_hotels': 12,
    'boutique_hotels': 13,
    'hostels': 14,
    'inns': 15,
    'motels': 16,
    'spa_hotels': 18,
    'bed_and_breakfasts': 19,
    'apartment_hotels': 21,
    'other': 20,
}
RENTAL_AMENITY_CODES = {
    'free_wifi': 29,
    'fitness_center': 16,
    'air_conditioned': 4,
    'kid_friendly': 21,
    'pool': 32,
    'pet_friendly': 24,
    'hot_tub': 2,
    'kitchen': 15,
    'patio_or_deck': 12,
    'outdoor_grill': 6,
    'crib': 18,
    'fireplace': 10,
}
RENTAL_TYPE_CODES = {'apartments': 1, 'chalets': 4, 'cottages': 5, 'houses': 8, 'houseboats': 9, 'villas': 10, 'other': 11}
# What the search lists: 1 hotels (vacation rentals mixed in unless the hotels-only flag is set), 2 vacation rentals.
SEARCH_MODE_HOTELS = 1
SEARCH_MODE_VACATION_RENTALS = 2
# Paging part of the search call. Without the leading 1 and the trailing 0 Google ignores half the filters, and
# the next page drops them all.
FIRST_PAGE = (1, None, None, None, None, None, NEXT_PAGE_VIEW_CODE, None, 0)
PAGE_TOKEN_INDEX = 1
# Google drops a filter in about one call in four; four attempts leave well under 1 % unfiltered.
MAX_FILTER_ATTEMPTS = 4
