from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_uses_group_product_without_appending_brand_again():
    terms = exact_research_terms({"brand": "Panini", "product": "Panini Prizm", "player": "P", "listings": [{}]})
    assert terms == ["P", "Panini Prizm"]
