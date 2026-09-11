from pathlib import Path


def test_sportscardspro_is_not_registered_as_governed_sold_provider():
    text = Path("src/card_scanner/opportunity_scanner.py").read_text(encoding="utf-8").lower()
    assert "sportscardspro" not in text
