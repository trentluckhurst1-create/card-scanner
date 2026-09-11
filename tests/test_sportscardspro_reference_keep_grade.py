from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_keeps_grade():
    assert exact_research_terms({"player": "P", "listings": [{"grade": 10}]}) == ["P", "10"]
