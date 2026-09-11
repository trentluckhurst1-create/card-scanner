from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_savings_metrics():
    assert exact_research_terms({"player": "P", "saving_vs_next_best_aud": 10, "saving_vs_median_pct": 20, "listings": [{}]}) == ["P"]
