from urllib.parse import parse_qs, urlparse
from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_reference_url_uses_q_parameter():
    qs = parse_qs(urlparse(search_url_for_exact_group({"player": "P", "listings": [{}]})).query)
    assert qs["q"] == ["P"]
