from card_scanner.sportscardspro_reference import exact_research_terms


def test_research_terms_are_trimmed():
    terms = exact_research_terms({"year": " 2024 ", "player": " Player ", "product": " Prizm ", "listings": [{}]})
    assert terms == ["2024", "Player", "Prizm"]
