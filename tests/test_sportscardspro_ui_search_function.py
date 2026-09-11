from pathlib import Path


def test_compare_ui_has_dedicated_sportscardspro_query_builder():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "function researchQuery(g)" in html
    assert "function sportscardsProLink(g)" in html
