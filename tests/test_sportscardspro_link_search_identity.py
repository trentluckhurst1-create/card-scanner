from card_scanner.sportscardspro_reference import exact_research_terms


def test_reference_terms_do_not_use_retailer_listing_title():
    terms = exact_research_terms({"player": "P", "listings": [{"title": "NOISY STORE TITLE", "card_number": "1"}]})
    assert "NOISY STORE TITLE" not in terms
    assert "1" in terms
