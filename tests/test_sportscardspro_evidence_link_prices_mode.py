from pathlib import Path


def test_browser_evidence_link_uses_prices_mode():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "search-products?type=prices&q=" in html
