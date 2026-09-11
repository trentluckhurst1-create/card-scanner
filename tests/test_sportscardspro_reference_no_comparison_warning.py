from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_comparison_warning():
    assert exact_research_terms({"player": "P", "comparison_warning": "warning", "listings": [{}]}) == ["P"]
