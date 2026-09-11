from urllib.parse import urlparse

from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_search_url_has_no_fragment():
    url = search_url_for_exact_group({"player": "Player", "listings": [{}]})
    assert urlparse(url).fragment == ""
