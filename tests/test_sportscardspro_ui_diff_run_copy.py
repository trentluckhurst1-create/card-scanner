from pathlib import Path


def test_ui_explicitly_excludes_different_print_runs():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "different print runs are not" in html
