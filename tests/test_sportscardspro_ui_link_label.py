from pathlib import Path


def test_research_link_label_names_provider():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert ">Check SportsCardsPro ↗</a>" in html
