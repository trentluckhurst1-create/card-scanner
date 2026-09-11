from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_exact_equivalent_flag():
    assert exact_research_terms({"player": "P", "exact_equivalent": True, "listings": [{}]}) == ["P"]
