from card_scanner.sportscardspro_reference import search_url_for_exact_group


def make(grade):
    return {"year": "2024", "player": "Player", "product": "Prizm", "listings": [{"card_number": "10", "grader": "PSA", "grade": grade}]}


def test_grade_changes_research_url():
    assert search_url_for_exact_group(make("9")) != search_url_for_exact_group(make("10"))
