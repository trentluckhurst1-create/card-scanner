from card_scanner.sportscardspro_reference import search_url_for_exact_group


def make(total):
    return {"year": "2024", "player": "Player", "product": "Prizm", "listings": [{"card_number": "10", "parallel": "Gold", "serial_total": total}]}


def test_print_run_changes_research_url():
    assert search_url_for_exact_group(make(10)) != search_url_for_exact_group(make(25))
