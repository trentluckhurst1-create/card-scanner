from pathlib import Path


def test_reference_module_contains_no_history_persistence():
    text = Path("src/card_scanner/sportscardspro_reference.py").read_text(encoding="utf-8").lower()
    assert "sqlite" not in text
    assert "persist" not in text
    assert "history" not in text
