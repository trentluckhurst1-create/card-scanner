from card_scanner.sportscardspro_reference import search_url_for_exact_group


def make(product):
    return {"year": "2024", "player": "P", "product": product, "listings": [{"card_number": "1"}]}


def test_product_changes_research_url():
    assert search_url_for_exact_group(make("Prizm")) != search_url_for_exact_group(make("Select"))
