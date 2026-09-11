from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_print_run_slash_is_url_encoded():
    url = search_url_for_exact_group({"player": "P", "listings": [{"serial_total": 99}]})
    assert "%2F99" in url
