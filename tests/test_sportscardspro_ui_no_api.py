from pathlib import Path


def test_compare_has_no_sportscardspro_api_call():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "sportscardspro.com/api" not in html
