from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_store_source():
    terms = exact_research_terms({"player": "P", "listings": [{"source": "UrbanEmpire"}]})
    assert terms == ["P"]
