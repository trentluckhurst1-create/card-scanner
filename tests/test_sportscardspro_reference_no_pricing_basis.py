from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_pricing_basis():
    assert exact_research_terms({"player": "P", "pricing_basis": "ACTIVE_ASKS_ONLY_NOT_FAIR_VALUE", "listings": [{}]}) == ["P"]
