from pathlib import Path


def test_ui_explicitly_says_1_of_10_vs_8_of_10_is_comparable():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "1/10 vs 8/10" in html
    assert "are comparable" in html
