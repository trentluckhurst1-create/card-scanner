from pathlib import Path


def test_compare_ui_explains_same_print_run_copy_numbers_are_comparable():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "different copy numbers from the same print run are comparable" in html
