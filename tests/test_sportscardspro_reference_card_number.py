from card_scanner.sportscardspro_reference import search_url_for_exact_group


def make(number):
    return {"year": "2024", "player": "Player", "product": "Prizm", "listings": [{"card_number": number}]}


def test_card_number_changes_research_url():
    assert search_url_for_exact_group(make("10")) != search_url_for_exact_group(make("11"))
