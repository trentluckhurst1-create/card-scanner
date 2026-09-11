from card_scanner.sportscardspro_reference import search_url_for_exact_group


def make(year):
    return {"year": year, "player": "P", "product": "Prizm", "listings": [{"card_number": "1"}]}


def test_year_changes_research_url():
    assert search_url_for_exact_group(make("2023")) != search_url_for_exact_group(make("2024"))
