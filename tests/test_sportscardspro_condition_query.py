from card_scanner.sportscardspro_reference import exact_research_terms


def test_graded_card_research_query_keeps_grader_and_grade():
    group = {
        "year": "2023",
        "player": "Player",
        "product": "Topps Chrome",
        "listings": [{
            "card_number": "42",
            "parallel": "Refractor",
            "serial_total": None,
            "grader": "PSA",
            "grade": "10",
        }],
    }
    terms = exact_research_terms(group)
    assert "PSA" in terms
    assert "10" in terms
