from card_scanner.sportscardspro_reference import SEARCH_URL


def test_search_url_constant_is_official_host():
    assert SEARCH_URL == "https://www.sportscardspro.com/search-products"
