from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_store_count():
    assert exact_research_terms({"player": "P", "store_count": 99, "listings": [{}]}) == ["P"]
