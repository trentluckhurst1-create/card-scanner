from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_source_field():
    assert exact_research_terms({"player": "P", "listings": [{"source": "Cherry"}]}) == ["P"]
