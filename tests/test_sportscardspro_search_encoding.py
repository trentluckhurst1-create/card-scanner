from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_search_url_encodes_parallel_and_serial_denominator():
    group = {
        "year": "2024",
        "player": "Test Player",
        "product": "Select AFL",
        "listings": [{"card_number": "A-1", "parallel": "Gold Wave", "serial_total": 10}],
    }
    url = search_url_for_exact_group(group)
    assert "Gold+Wave" in url
    assert "%2F10" in url
