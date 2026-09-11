from card_scanner.sportscardspro_reference import exact_research_terms


def test_blank_terms_are_omitted():
    assert exact_research_terms({"year": " ", "player": "P", "product": "", "listings": [{}]}) == ["P"]
