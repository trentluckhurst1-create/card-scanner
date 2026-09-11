from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_reference_url_is_plain_string():
    assert isinstance(search_url_for_exact_group({"player": "P", "listings": [{}]}), str)
