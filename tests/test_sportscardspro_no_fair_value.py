from pathlib import Path


def test_sportscardspro_reference_module_has_no_valuation_or_buy_logic():
    text = Path("src/card_scanner/sportscardspro_reference.py").read_text(encoding="utf-8").lower()
    assert "fair_value" not in text
    assert "strong_buy" not in text
    assert "valuation" not in text
