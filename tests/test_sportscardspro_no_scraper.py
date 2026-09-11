from pathlib import Path


def test_no_sportscardspro_scraper_source_is_added():
    assert not Path("src/card_scanner/sources/sportscardspro.py").exists()
