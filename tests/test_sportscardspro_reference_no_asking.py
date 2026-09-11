from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_asking_price():
    assert exact_research_terms({"player": "P", "listings": [{"asking_price": 99}]}) == ["P"]
