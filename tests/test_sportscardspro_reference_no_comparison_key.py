from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_internal_comparison_key():
    assert exact_research_terms({"player": "P", "comparison_key": "secret-internal-key", "listings": [{}]}) == ["P"]
