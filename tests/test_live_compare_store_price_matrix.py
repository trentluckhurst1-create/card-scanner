from pathlib import Path


def test_live_compare_shows_store_by_store_price_differences():
    html = (Path(__file__).resolve().parents[1] / "docs" / "live-compare.html").read_text(encoding="utf-8")

    assert "Compare card prices between stores" in html
    assert "price-matrix" in html
    assert "Difference vs cheapest" in html
    assert "% above cheapest" in html
    assert "CHEAPEST" in html
    assert "priceOf(l)" in html
    assert "diff/low" in html
    assert "above cheapest" in html
    assert "lowest active ask" in html.lower()
    assert "active asking price only" in html.lower()
    assert "fair value" in html.lower()
