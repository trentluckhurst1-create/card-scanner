from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_search_helper_returns_url_without_mutating_group():
    group = {"player": "P", "listings": [{}]}
    before = repr(group)
    search_url_for_exact_group(group)
    assert repr(group) == before
