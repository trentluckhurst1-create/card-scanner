from card_scanner.sportscardspro_reference import search_url_for_exact_group


def make(player):
    return {"year": "2024", "player": player, "product": "Prizm", "listings": [{"card_number": "1"}]}


def test_player_changes_research_url():
    assert search_url_for_exact_group(make("A")) != search_url_for_exact_group(make("B"))
