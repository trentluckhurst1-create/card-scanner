from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_landed_aud():
    assert exact_research_terms({"player": "P", "listings": [{"landed_aud": 99}]}) == ["P"]
