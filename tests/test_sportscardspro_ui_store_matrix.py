from pathlib import Path


def test_store_price_matrix_remains_primary_comparison():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "Price AUD" in html
    assert "% above cheapest" in html
    assert "CHEAPEST" in html
