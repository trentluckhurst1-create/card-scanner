from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_retailer_currency():
    assert exact_research_terms({"player": "P", "listings": [{"currency": "AUD"}]}) == ["P"]
