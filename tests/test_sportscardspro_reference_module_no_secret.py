from pathlib import Path


def test_reference_module_contains_no_authentication_token():
    text = Path("src/card_scanner/sportscardspro_reference.py").read_text(encoding="utf-8").lower()
    assert "token" not in text
    assert "api_key" not in text
