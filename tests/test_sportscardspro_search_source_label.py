from pathlib import Path


def test_compare_labels_sportscardspro_as_research_source():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "Recent-sales research" in html
    assert "external research source" in html
