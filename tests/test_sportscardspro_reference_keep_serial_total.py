from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_keeps_serial_total_as_slash_denominator():
    assert exact_research_terms({"player": "P", "listings": [{"serial_total": 170}]}) == ["P", "/170"]
