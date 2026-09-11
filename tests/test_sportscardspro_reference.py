from card_scanner.sportscardspro_reference import exact_research_terms, search_url_for_exact_group


def group(serial_total=10):
    return {
        "year": "2022",
        "player": "James Tunstill",
        "product": "AFL Optimum",
        "listings": [{
            "card_number": "OA-JT",
            "parallel": "Optimum Plus",
            "serial_current": 8,
            "serial_total": serial_total,
            "grader": None,
            "grade": None,
        }],
    }


def test_reference_query_keeps_print_run_but_ignores_copy_number():
    terms = exact_research_terms(group(10))
    assert "/10" in terms
    assert "8" not in terms


def test_different_print_run_changes_reference_query():
    assert exact_research_terms(group(10)) != exact_research_terms(group(25))


def test_search_url_targets_sportscardspro_price_search():
    url = search_url_for_exact_group(group())
    assert url.startswith("https://www.sportscardspro.com/search-products?")
    assert "type=prices" in url
    assert "James+Tunstill" in url
