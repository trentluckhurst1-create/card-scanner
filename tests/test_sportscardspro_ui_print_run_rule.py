from pathlib import Path


def test_compare_ui_says_different_print_runs_are_not_comparable():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "different print runs are not" in html
