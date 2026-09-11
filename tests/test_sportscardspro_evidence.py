from pathlib import Path


def _html() -> str:
    return Path("docs/live-compare.html").read_text(encoding="utf-8")


def test_sportscardspro_is_external_research_only():
    html = _html()
    assert "Check SportsCardsPro" in html
    assert "its proprietary pricing data is not copied into this public app" in html
    assert "sportscardspro.json" not in html.lower()
    assert "<iframe" not in html.lower()


def test_sportscardspro_does_not_enter_retailer_price_math():
    html = _html()
    matrix = html[html.index("function matrix(listings)"):html.index("function card(")]
    render = html[html.index("function render()"):html.index("async function load()")]
    assert "sportscards" not in matrix.lower()
    assert "SportsCardsPro" not in render
    assert "lowest_active_ask_aud" in render
    assert "spread_aud" in render


def test_research_query_uses_print_run_not_individual_copy_number():
    html = _html()
    query = html[html.index("function researchQuery(g)"):html.index("function sportscardsProLink", html.index("function researchQuery(g)"))]
    assert "sample.serial_total" in query
    assert "serial_number" not in query
    assert "serial_copy" not in query


def test_serial_rule_and_buy_governance_are_visible():
    html = _html()
    assert "1/10 vs 8/10" in html
    assert "different print runs are not" in html.lower()
    assert "cannot create BUY or STRONG BUY" in html
