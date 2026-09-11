from card_scanner.sportscardspro_reference import search_url_for_exact_group


def make(copy_no):
    return {
        "year": "2025",
        "player": "Player Name",
        "product": "Panini Prizm",
        "listings": [{
            "card_number": "101",
            "parallel": "Gold",
            "serial_current": copy_no,
            "serial_total": 10,
            "grader": None,
            "grade": None,
        }],
    }


def test_different_copy_numbers_same_print_run_generate_same_research_url():
    assert search_url_for_exact_group(make(1)) == search_url_for_exact_group(make(8))
