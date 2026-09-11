from card_scanner.sportscardspro_reference import exact_research_terms


def test_helper_does_not_emit_boolean_flags():
    terms = exact_research_terms({"player": "P", "listings": [{"rookie": True, "autograph": True, "memorabilia": False}]})
    assert terms == ["P"]
