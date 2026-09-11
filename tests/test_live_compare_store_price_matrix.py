from pathlib import Path


def test_live_compare_shows_store_by_store_price_differences_for_exact_cards_only():
    html = (Path(__file__).resolve().parents[1] / "docs" / "live-compare.html").read_text(encoding="utf-8")

    assert "Compare the exact same card between stores" in html
    assert 'class="matrix"' in html
    assert "Difference" in html
    assert "% above cheapest" in html
    assert "CHEAPEST" in html
    assert "priceOf(l)" in html
    assert "d/low" in html
    assert "g.comparison_type==='EXACT_CARD'" in html
    assert "Active asks are comparison evidence only" in html
    assert "fair value" in html.lower()
