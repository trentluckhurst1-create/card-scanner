from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_lowest_active_ask():
    assert exact_research_terms({"player": "P", "lowest_active_ask_aud": 10, "listings": [{}]}) == ["P"]
