from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_cheapest_external_id():
    assert exact_research_terms({"player": "P", "cheapest_external_id": "123", "listings": [{}]}) == ["P"]
