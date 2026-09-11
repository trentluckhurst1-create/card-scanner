from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_same_exact_group_produces_same_url():
    group = {"year": "2024", "player": "Player", "product": "Prizm", "listings": [{"card_number": "1", "parallel": "Gold", "serial_total": 10}]}
    assert search_url_for_exact_group(group) == search_url_for_exact_group(group)
