from pathlib import Path


PAGE = Path("docs/live-compare.html")


def test_sportscardspro_is_external_research_not_republished_price_data():
    html = PAGE.read_text(encoding="utf-8")
    assert "Check SportsCardsPro" in html
    assert "sportscardspro.com/search-products" in html
    assert "historic-sale data stays on their site" in html
    assert "is not republished here" in html


def test_numbered_card_copy_rule_is_explained_in_compare_ui():
    html = PAGE.read_text(encoding="utf-8")
    assert "1/10 vs 8/10" in html
    assert "different print runs are not" in html
    assert "same serial print run" in html
