from pathlib import Path


def test_reference_module_does_not_implement_sold_provider_interface():
    text = Path("src/card_scanner/sportscardspro_reference.py").read_text(encoding="utf-8")
    assert "SoldCompProvider" not in text
    assert "fetch_sold" not in text
