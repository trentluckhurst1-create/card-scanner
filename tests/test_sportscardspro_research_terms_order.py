from card_scanner.sportscardspro_reference import exact_research_terms


def test_research_terms_start_with_core_identity():
    terms = exact_research_terms({
        "year": "2024", "player": "Player Name", "product": "Topps Chrome",
        "listings": [{"card_number": "12", "parallel": "Gold"}],
    })
    assert terms[:3] == ["2024", "Player Name", "Topps Chrome"]
