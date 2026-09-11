from pathlib import Path


def test_public_sportscardspro_integration_contains_no_api_token_parameter():
    paths = [
        Path("docs/live-compare.html"),
        Path("docs/sportscardspro/index.html"),
        Path("src/card_scanner/sportscardspro_reference.py"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "SPORTSCARDSPRO_API_KEY" not in combined
    assert "?t=" not in combined
    assert "&t=" not in combined
