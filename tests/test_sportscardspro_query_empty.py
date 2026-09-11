from card_scanner.sportscardspro_reference import exact_research_terms


def test_sparse_group_does_not_emit_none_tokens():
    terms = exact_research_terms({"player": "Player", "listings": [{}]})
    assert terms == ["Player"]
    assert "None" not in terms
