from card_scanner.sportscardspro_reference import exact_research_terms


def test_serial_current_is_ignored_even_when_present():
    group = {"player": "P", "listings": [{"serial_current": 1, "serial_total": 10}]}
    assert exact_research_terms(group) == ["P", "/10"]
