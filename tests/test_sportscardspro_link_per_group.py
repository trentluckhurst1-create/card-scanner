from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_different_players_generate_different_research_links():
    a = {"year": "2024", "player": "Player A", "product": "Prizm", "listings": [{"card_number": "1"}]}
    b = {"year": "2024", "player": "Player B", "product": "Prizm", "listings": [{"card_number": "1"}]}
    assert search_url_for_exact_group(a) != search_url_for_exact_group(b)
