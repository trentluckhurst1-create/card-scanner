from urllib.parse import parse_qs, urlparse
from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_generated_research_url_has_no_auth_token_parameter():
    qs = parse_qs(urlparse(search_url_for_exact_group({"player": "P", "listings": [{}]})).query)
    assert "t" not in qs
    assert "token" not in qs
