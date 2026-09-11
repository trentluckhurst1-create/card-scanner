from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_listing_url():
    assert exact_research_terms({"player": "P", "listings": [{"url": "https://example.com"}]}) == ["P"]
