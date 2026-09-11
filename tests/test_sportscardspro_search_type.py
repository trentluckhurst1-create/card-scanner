from urllib.parse import parse_qs, urlparse

from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_reference_url_uses_prices_search_mode():
    parsed = urlparse(search_url_for_exact_group({"player": "Player", "listings": [{}]}))
    query = parse_qs(parsed.query)
    assert query["type"] == ["prices"]
