from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_next_best_store():
    assert exact_research_terms({"player": "P", "next_best_store": "Boop", "listings": [{}]}) == ["P"]
