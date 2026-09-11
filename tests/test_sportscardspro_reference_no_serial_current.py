from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_ignores_serial_current_but_keeps_total():
    assert exact_research_terms({"player": "P", "listings": [{"serial_current": 8, "serial_total": 10}]}) == ["P", "/10"]
