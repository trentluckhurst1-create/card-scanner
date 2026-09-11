from pathlib import Path


def test_sportscardspro_research_is_attached_to_exact_compare_not_catalogue():
    compare = Path("docs/live-compare.html").read_text(encoding="utf-8")
    catalogue = Path("docs/catalogue.html").read_text(encoding="utf-8")
    assert "Check SportsCardsPro" in compare
    assert "Check SportsCardsPro" not in catalogue
