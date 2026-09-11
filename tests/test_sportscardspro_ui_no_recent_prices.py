from pathlib import Path


def test_ui_contains_no_hardcoded_sportscardspro_recent_sale_amounts():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "SportsCardsPro recent sale $" not in html
    assert "SportsCardsPro value $" not in html
