from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_does_not_append_sport_label():
    assert exact_research_terms({"sport": "NFL", "player": "P", "listings": [{}]}) == ["P"]
