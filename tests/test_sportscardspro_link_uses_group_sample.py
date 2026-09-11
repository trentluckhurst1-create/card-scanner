from card_scanner.sportscardspro_reference import exact_research_terms


def test_first_exact_listing_supplies_structured_discriminators():
    group = {"player": "P", "listings": [{"card_number": "7", "parallel": "Gold", "serial_total": 50}]}
    assert exact_research_terms(group)[-3:] == ["7", "Gold", "/50"]
