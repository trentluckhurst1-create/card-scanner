from pathlib import Path


def test_browser_link_targets_sportscardspro_price_search():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "https://www.sportscardspro.com/search-products?type=prices&q=" in html
