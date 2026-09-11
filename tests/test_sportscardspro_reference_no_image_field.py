from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_image_url_field():
    assert exact_research_terms({"player": "P", "listings": [{"image_url": "https://example.com/a.jpg"}]}) == ["P"]
