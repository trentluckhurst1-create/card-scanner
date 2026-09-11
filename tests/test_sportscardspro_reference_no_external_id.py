from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_external_id():
    assert exact_research_terms({"player": "P", "listings": [{"external_id": "abc"}]}) == ["P"]
