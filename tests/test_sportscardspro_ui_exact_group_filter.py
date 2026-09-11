from pathlib import Path


def test_compare_still_filters_only_exact_card_groups():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "g.comparison_type==='EXACT_CARD'" in html
    assert "Number(g.store_count||0)>=2" in html
