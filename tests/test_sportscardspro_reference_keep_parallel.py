from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_keeps_parallel():
    assert exact_research_terms({"player": "P", "listings": [{"parallel": "Gold Wave"}]}) == ["P", "Gold Wave"]
