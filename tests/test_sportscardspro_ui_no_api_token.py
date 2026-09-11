from pathlib import Path


def test_compare_ui_has_no_sportscardspro_token_parameter():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "?t=" not in html
    assert "&t=" not in html
