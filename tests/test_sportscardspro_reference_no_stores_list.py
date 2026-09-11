from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_stores_list():
    assert exact_research_terms({"player": "P", "stores": ["Cherry", "Boop"], "listings": [{}]}) == ["P"]
