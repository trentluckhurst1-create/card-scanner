from pathlib import Path


def test_research_button_is_explicit_about_destination():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "Check SportsCardsPro ↗" in html
