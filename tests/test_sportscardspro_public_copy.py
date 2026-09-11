from pathlib import Path


def test_compare_copy_separates_active_asks_from_sales_research():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "Active asks are comparison evidence only" in html
    assert "Recent-sales research" in html
    assert "Check this exact card/print-run on SportsCardsPro" in html
