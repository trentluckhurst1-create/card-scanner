from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_helper_uses_prices_search_type():
    assert "type=prices" in search_url_for_exact_group({"player": "P", "listings": [{}]})
