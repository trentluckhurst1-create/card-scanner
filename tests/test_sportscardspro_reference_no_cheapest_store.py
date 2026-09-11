from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_cheapest_store():
    assert exact_research_terms({"player": "P", "cheapest_store": "Cherry", "listings": [{}]}) == ["P"]
