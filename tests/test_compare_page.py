from pathlib import Path


def test_compare_page_exposes_governed_cross_store_price_comparison_ui():
    html = (Path(__file__).resolve().parents[1] / "docs" / "compare.html").read_text(encoding="utf-8")

    assert "Compare Card Prices Across Stores" in html
    assert "EXACT CARD" in html
    assert "RELATED VARIANTS" in html
    assert "PLAYER / YEAR" in html
    assert "Cheapest" in html
    assert "Next best" in html
    assert "Median" in html
    assert "Highest" in html
    assert "Spread" in html
    assert "market.json?ts=" in html
    assert "active_price_comparisons" in html
    assert "V2 client comparison from current active catalogue" in html
    assert "Active asking prices are comparison evidence only" in html
    assert "fair value" in html.casefold()


def test_compare_page_never_labels_related_variants_as_exact():
    html = (Path(__file__).resolve().parents[1] / "docs" / "compare.html").read_text(encoding="utf-8")

    assert "RELATED ACTIVE LISTINGS" not in html
    assert "Same Product Variants and Player/Year Market are related-market context only" in html
    assert "type==='EXACT_CARD'" in html
