from card_scanner.sportscardspro_reference import exact_research_terms


def test_reference_helper_documents_copy_number_rule():
    doc = exact_research_terms.__doc__ or ""
    assert "copy number is intentionally excluded" in doc
    assert "/10 and /25" in doc
