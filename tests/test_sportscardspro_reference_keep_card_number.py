from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_keeps_card_number():
    assert exact_research_terms({"player": "P", "listings": [{"card_number": "OA-JT"}]}) == ["P", "OA-JT"]
