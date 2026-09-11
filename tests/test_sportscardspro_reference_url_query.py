from urllib.parse import parse_qs, urlparse

from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_url_query_contains_year_player_product():
    url = search_url_for_exact_group({"year": "2022", "player": "James Tunstill", "product": "AFL Optimum", "listings": [{}]})
    q = parse_qs(urlparse(url).query)["q"][0]
    assert "2022" in q
    assert "James Tunstill" in q
    assert "AFL Optimum" in q
