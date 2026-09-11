from pathlib import Path


def test_explainer_calls_sportscardspro_market_evidence():
    html = Path("docs/sportscardspro/index.html").read_text(encoding="utf-8")
    assert "SportsCardsPro market evidence" in html
