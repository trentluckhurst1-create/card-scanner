from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_listing_count():
    assert exact_research_terms({"player": "P", "listing_count": 5, "listings": [{}]}) == ["P"]
