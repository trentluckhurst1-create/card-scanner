from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_active_price_spread():
    assert exact_research_terms({"player": "P", "spread_aud": 123, "listings": [{}]}) == ["P"]
