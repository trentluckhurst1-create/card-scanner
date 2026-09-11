from pathlib import Path


def test_related_variant_rendering_is_not_present_on_exact_compare_page():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "comparison_type==='SAME_PRODUCT_VARIANTS'" not in html
    assert "comparison_type==='PLAYER_YEAR_MARKET'" not in html
