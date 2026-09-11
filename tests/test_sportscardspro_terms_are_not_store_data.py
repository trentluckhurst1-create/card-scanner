from card_scanner.sportscardspro_reference import search_url_for_exact_group


def test_retailer_source_does_not_change_sportscardspro_research_identity():
    base = {"year": "2024", "player": "Player", "product": "Prizm"}
    a = {**base, "listings": [{"source": "Cherry", "card_number": "1"}]}
    b = {**base, "listings": [{"source": "Boop", "card_number": "1"}]}
    assert search_url_for_exact_group(a) == search_url_for_exact_group(b)
