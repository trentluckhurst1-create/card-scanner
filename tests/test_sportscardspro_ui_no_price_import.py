from pathlib import Path


def test_compare_page_does_not_load_sportscardspro_script_or_json():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8").lower()
    assert "sportscardspro.json" not in html
    assert "src=\"https://www.sportscardspro.com" not in html
