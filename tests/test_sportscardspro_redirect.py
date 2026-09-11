from pathlib import Path


def test_sportscardspro_redirect_targets_explainer():
    html = Path("docs/sportscardspro.html").read_text(encoding="utf-8")
    assert "url=./sportscardspro/" in html
