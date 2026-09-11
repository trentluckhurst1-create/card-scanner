from pathlib import Path


def test_compare_has_no_sportscardspro_csv_feed():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "sportscardspro.csv" not in html.lower()
