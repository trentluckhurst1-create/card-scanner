from pathlib import Path


def test_compare_route_uses_automated_active_market_page():
    route = (Path(__file__).resolve().parents[1] / "docs" / "compare" / "index.html").read_text(encoding="utf-8")
    assert "../live-compare.html" in route


def test_live_compare_page_prefers_active_market_and_falls_back_to_governed_feed():
    html = (Path(__file__).resolve().parents[1] / "docs" / "live-compare.html").read_text(encoding="utf-8")
    assert "fetchJson('active_market.json')" in html
    assert "fetchJson('market.json')" in html
    assert "automated active-market feed" in html
    assert "governed local-feed fallback" in html
    assert "Active asks are comparison evidence only" in html
    assert "cannot create BUY or STRONG_BUY" in html


def test_live_compare_page_exposes_source_health_and_price_columns():
    html = (Path(__file__).resolve().parents[1] / "docs" / "live-compare.html").read_text(encoding="utf-8")
    for text in ("Cherry", "Sports Card Store", "Gimko", "Urban Empire", "Cheapest", "Next best", "Median", "Highest", "Price spread"):
        assert text in html
    assert "unavailable to cloud scan" in html
    assert "EXACT CARD" in html
    assert "RELATED VARIANTS" in html
    assert "PLAYER / YEAR" in html
