from pathlib import Path


def test_public_pages_visibly_name_and_link_sportscardspro():
    compare = Path("docs/live-compare.html").read_text(encoding="utf-8")
    explainer = Path("docs/sportscardspro/index.html").read_text(encoding="utf-8")
    assert "SportsCardsPro" in compare
    assert "https://www.sportscardspro.com/" in compare
    assert "SportsCardsPro" in explainer
    assert "https://www.sportscardspro.com/" in explainer
