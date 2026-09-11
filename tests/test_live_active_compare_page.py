from pathlib import Path


def test_compare_route_uses_automated_active_market_page():
    route = (Path(__file__).resolve().parents[1] / "docs" / "compare" / "index.html").read_text(encoding="utf-8")
    assert "../live-compare.html" in route


def test_live_compare_page_uses_exact_comparison_feed_and_preserves_governance():
    html = (Path(__file__).resolve().parents[1] / "docs" / "live-compare.html").read_text(encoding="utf-8")
    assert "comparison.json" in html
    assert "g.comparison_type==='EXACT_CARD'" in html
    assert "Active asks are comparison evidence only" in html
    assert "cannot create BUY or STRONG BUY" in html


def test_live_compare_page_exposes_exact_price_columns_only():
    html = (Path(__file__).resolve().parents[1] / "docs" / "live-compare.html").read_text(encoding="utf-8")
    for text in ("CHEAPEST", "Difference", "% above cheapest", "EXACT SAME CARD"):
        assert text in html
    assert "Different variants are deliberately not compared" in html
    assert "All comparison types" not in html
