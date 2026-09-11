from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_shipping():
    assert exact_research_terms({"player": "P", "listings": [{"shipping": 9.95}]}) == ["P"]
