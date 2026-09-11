from card_scanner.sportscardspro_reference import exact_research_terms


def test_query_does_not_append_boolean_flags_as_strings():
    group = {
        "year": "2024", "player": "Player", "product": "Prizm",
        "listings": [{"card_number": "1", "autograph": True, "rookie": True}],
    }
    terms = exact_research_terms(group)
    assert "True" not in terms
    assert "False" not in terms
