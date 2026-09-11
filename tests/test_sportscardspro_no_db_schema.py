from pathlib import Path


def test_database_schema_has_no_sportscardspro_table():
    text = Path("src/card_scanner/db.py").read_text(encoding="utf-8").lower()
    assert "sportscardspro" not in text
