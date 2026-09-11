from pathlib import Path


def test_sportscardspro_is_not_in_cheapest_store_calculation():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    matrix_start = html.index("function matrix(listings)")
    matrix_end = html.index("function card(", matrix_start)
    matrix_fn = html[matrix_start:matrix_end]
    group_start = html.index("function group(g)")
    group_end = html.index("function render()", group_start)
    group_fn = html[group_start:group_end]
    assert "SportsCardsPro" not in matrix_fn
    assert "priceOf" in matrix_fn
    assert "${evidence(g)}" in group_fn
