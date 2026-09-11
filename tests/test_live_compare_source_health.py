from pathlib import Path


def test_live_compare_is_not_a_broad_source_catalogue():
    html = (Path(__file__).resolve().parents[1] / "docs" / "live-compare.html").read_text(encoding="utf-8")

    assert "Exact-card store price comparison" in html
    assert "exact same card between stores" in html
    assert "Different parallels" in html
    assert "g.comparison_type==='EXACT_CARD'" in html
    assert "Different variants are deliberately not compared" in html
