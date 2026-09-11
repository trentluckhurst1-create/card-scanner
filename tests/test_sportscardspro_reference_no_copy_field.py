from pathlib import Path


def test_reference_helper_does_not_read_serial_current():
    text = Path("src/card_scanner/sportscardspro_reference.py").read_text(encoding="utf-8")
    assert 'sample.get("serial_current")' not in text
