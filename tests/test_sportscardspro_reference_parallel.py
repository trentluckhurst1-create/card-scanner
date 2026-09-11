from card_scanner.sportscardspro_reference import search_url_for_exact_group


def make(parallel):
    return {"year": "2024", "player": "Player", "product": "Prizm", "listings": [{"card_number": "10", "parallel": parallel}]}


def test_parallel_changes_research_url():
    assert search_url_for_exact_group(make("Gold")) != search_url_for_exact_group(make("Silver"))
