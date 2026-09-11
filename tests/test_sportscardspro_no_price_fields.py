from card_scanner.sportscardspro_reference import exact_research_terms


def test_reference_helper_returns_only_search_terms_not_prices():
    result = exact_research_terms({"player": "Player", "listings": [{}]})
    assert isinstance(result, list)
    assert all(isinstance(item, str) for item in result)
