from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_highest_active_ask():
    assert exact_research_terms({"player": "P", "highest_active_ask_aud": 99, "listings": [{}]}) == ["P"]
