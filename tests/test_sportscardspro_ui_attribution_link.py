from pathlib import Path


def test_research_panel_contains_visible_sportscardspro_name_and_link():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "SportsCardsPro" in html
    assert "sportscardsProLink(g)" in html
