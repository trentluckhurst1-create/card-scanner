from card_scanner.sportscardspro_reference import exact_research_terms


def test_terms_do_not_include_retailer_source_name():
    terms = exact_research_terms({"player": "Player", "listings": [{"source": "Cherry"}]})
    assert "Cherry" not in terms
