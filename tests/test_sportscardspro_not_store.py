from pathlib import Path


def test_sportscardspro_is_not_added_to_cloud_retailer_scan():
    text = Path("scripts/publish_active_market.py").read_text(encoding="utf-8")
    assert "sportscardspro" not in text.lower()


def test_sportscardspro_is_not_added_to_local_acquisition_source_factory():
    text = Path("src/card_scanner/cli.py").read_text(encoding="utf-8")
    assert "sportscardspro" not in text.lower()
