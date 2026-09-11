from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_cheapest_url():
    assert exact_research_terms({"player": "P", "cheapest_url": "https://shop.example", "listings": [{}]}) == ["P"]
