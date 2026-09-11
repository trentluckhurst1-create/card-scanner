from pathlib import Path


def _html() -> str:
    return (Path(__file__).resolve().parents[1] / "docs" / "live-compare.html").read_text(encoding="utf-8")


def test_exact_compare_links_direct_sold_research_sources():
    html = _html()
    assert "function ebaySoldLink(g)" in html
    assert "LH_Complete=1&LH_Sold=1" in html
    assert "Fanatics Sold History" in html
    assert "https://sales-history.fanaticscollect.com/" in html
    assert "130 Point Comps" in html
    assert "Check SportsCardsPro" in html


def test_external_sold_sources_do_not_enter_store_price_math():
    html = _html()
    matrix = html[html.index("function matrix(listings)"):html.index("function card(")]
    for term in ("ebaySoldLink", "fanaticsSoldLink", "point130Link", "sportscardsProLink"):
        assert term not in matrix


def test_sold_research_uses_same_exact_card_query():
    html = _html()
    query = html[html.index("function researchQuery(g)"):html.index("function ebayLink(g)")]
    assert "sample.serial_total" in query
    assert "serial_current" not in query
