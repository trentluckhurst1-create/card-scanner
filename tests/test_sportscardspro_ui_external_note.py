from pathlib import Path


def test_ui_explains_sportscardspro_data_stays_external():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "stays on their site" in html
