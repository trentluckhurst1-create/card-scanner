from urllib.parse import urlparse

from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_reference_link_uses_official_sportscardspro_host():
    url = search_url_for_exact_group({"player": "Player", "listings": [{}]})
    assert urlparse(url).netloc == "www.sportscardspro.com"
