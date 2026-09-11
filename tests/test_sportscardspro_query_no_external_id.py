from card_scanner.sportscardspro_reference import exact_research_terms


def test_research_terms_ignore_retailer_external_id():
    terms = exact_research_terms({"player": "P", "listings": [{"external_id": "999999"}]})
    assert "999999" not in terms
