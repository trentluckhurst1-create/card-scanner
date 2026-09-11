from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_image_url():
    terms = exact_research_terms({"player": "P", "listings": [{"image_url": "https://example.com/card.jpg"}]})
    assert terms == ["P"]
