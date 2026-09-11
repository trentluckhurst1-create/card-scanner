from card_scanner.sportscardspro_reference import exact_research_terms


def test_exact_research_terms_include_card_number_and_parallel():
    group = {
        "year": "2024",
        "player": "Player",
        "product": "Prizm",
        "listings": [{"card_number": "101", "parallel": "Blue Ice"}],
    }
    terms = exact_research_terms(group)
    assert "101" in terms
    assert "Blue Ice" in terms
