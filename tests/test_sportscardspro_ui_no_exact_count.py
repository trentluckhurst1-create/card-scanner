from pathlib import Path


def test_exact_count_comes_from_comparison_feed_only():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "$('exact').textContent=groups.length" in html
