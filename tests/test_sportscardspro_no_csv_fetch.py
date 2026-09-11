from pathlib import Path


def test_public_integration_does_not_download_sportscardspro_csv():
    combined = "\n".join(Path(p).read_text(encoding="utf-8").lower() for p in ["docs/live-compare.html", "src/card_scanner/sportscardspro_reference.py"])
    assert "download-price" not in combined
    assert ".csv" not in combined
