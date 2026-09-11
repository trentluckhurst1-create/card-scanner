from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_asking_and_landed_prices():
    terms = exact_research_terms({"player": "P", "listings": [{"asking_price": 50, "landed_aud": 60}]})
    assert terms == ["P"]
