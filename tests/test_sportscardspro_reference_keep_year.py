from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_keeps_year():
    assert exact_research_terms({"year": 2024, "player": "P", "listings": [{}]}) == ["2024", "P"]
