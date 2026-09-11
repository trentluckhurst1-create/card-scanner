from card_scanner.sportscardspro_reference import exact_research_terms


def test_research_terms_ignore_retailer_listing_url():
    terms = exact_research_terms({"player": "P", "listings": [{"url": "https://shop.example/card"}]})
    assert not any("shop.example" in term for term in terms)
