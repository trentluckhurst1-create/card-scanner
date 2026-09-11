from urllib.parse import urlparse
from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_reference_url_uses_search_products_path():
    assert urlparse(search_url_for_exact_group({"player": "P", "listings": [{}]})).path == "/search-products"
