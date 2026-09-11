from pathlib import Path


def test_compare_has_no_sportscardspro_json_feed():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "sportscardspro.json" not in html.lower()
