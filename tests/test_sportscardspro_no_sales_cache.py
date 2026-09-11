from pathlib import Path


def test_no_sportscardspro_sales_cache_or_feed_file_exists():
    forbidden = [
        Path("docs/sportscardspro_sales.json"),
        Path("docs/sportscardspro_prices.json"),
        Path("data/sportscardspro_sales.json"),
        Path("data/sportscardspro_prices.json"),
    ]
    assert not any(path.exists() for path in forbidden)
