from pathlib import Path


def test_compare_only_fetches_own_comparison_feed():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert html.count("fetch(") == 1
    assert "fetch('./comparison.json" in html
