from pathlib import Path


def test_reference_helper_reads_serial_total():
    text = Path("src/card_scanner/sportscardspro_reference.py").read_text(encoding="utf-8")
    assert 'sample.get("serial_total")' in text
