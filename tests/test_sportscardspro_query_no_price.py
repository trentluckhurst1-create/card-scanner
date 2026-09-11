from card_scanner.sportscardspro_reference import exact_research_terms


def test_research_terms_ignore_active_asking_price():
    terms = exact_research_terms({"player": "P", "listings": [{"asking_price": 999.99, "landed_aud": 1000.00}]})
    assert "999.99" not in terms
    assert "1000.0" not in terms
