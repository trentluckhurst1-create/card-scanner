from pathlib import Path


def test_public_code_contains_no_sportscardspro_api_path():
    for path in [Path("docs/live-compare.html"), Path("src/card_scanner/sportscardspro_reference.py")]:
        assert "/api/product" not in path.read_text(encoding="utf-8")
