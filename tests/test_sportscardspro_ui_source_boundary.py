from pathlib import Path


def test_explainer_calls_sportscardspro_not_acquisition_retailer():
    html = Path("docs/sportscardspro/index.html").read_text(encoding="utf-8")
    assert "not as an acquisition retailer" in html
