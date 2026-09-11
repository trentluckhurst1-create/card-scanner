from pathlib import Path


def test_compare_guard_says_sportscardspro_data_not_copied():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "proprietary pricing data is not copied into this public app" in html
