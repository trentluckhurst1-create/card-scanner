from pathlib import Path


def test_compare_does_not_auto_redirect_to_sportscardspro():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8").lower()
    assert 'http-equiv="refresh"' not in html
