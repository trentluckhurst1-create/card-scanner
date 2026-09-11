from card_scanner.sportscardspro_reference import search_url_for_exact_group


def group(copy_no):
    return {"year": "2024", "player": "P", "product": "Prizm", "listings": [{"card_number": "1", "parallel": "Gold", "serial_current": copy_no, "serial_total": 10}]}


def test_1_of_10_and_8_of_10_share_research_target():
    assert search_url_for_exact_group(group(1)) == search_url_for_exact_group(group(8))
