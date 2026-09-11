from pathlib import Path


def test_active_market_publisher_does_not_register_sportscardspro_source():
    text = Path("scripts/publish_active_market.py").read_text(encoding="utf-8").lower()
    assert '"sportscardspro"' not in text
    assert "'sportscardspro'" not in text
