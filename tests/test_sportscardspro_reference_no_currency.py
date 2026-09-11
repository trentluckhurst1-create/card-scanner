from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_reference_url_does_not_force_currency():
    url = search_url_for_exact_group({"player": "P", "listings": [{}]}).lower()
    assert "currency=" not in url
    assert "aud" not in url
    assert "usd" not in url
