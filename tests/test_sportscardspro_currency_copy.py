from pathlib import Path


def test_compare_does_not_label_sportscardspro_research_as_aud_price():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "SportsCardsPro AUD" not in html
    assert "SportsCardsPro price AUD" not in html
