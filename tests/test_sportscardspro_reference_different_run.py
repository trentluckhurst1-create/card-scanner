from card_scanner.sportscardspro_reference import search_url_for_exact_group


def group(total):
    return {"year": "2024", "player": "P", "product": "Prizm", "listings": [{"card_number": "1", "parallel": "Gold", "serial_current": 1, "serial_total": total}]}


def test_1_of_10_and_1_of_25_do_not_share_research_target():
    assert search_url_for_exact_group(group(10)) != search_url_for_exact_group(group(25))
