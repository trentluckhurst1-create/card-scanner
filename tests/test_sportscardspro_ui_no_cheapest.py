from pathlib import Path


def test_sportscardspro_is_not_in_cheapest_store_calculation():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    start = html.index("function group(g)")
    end = html.index("function render()", start)
    group_fn = html[start:end]
    assert "sportscardsProLink" in group_fn
    assert "priceOf" in group_fn
    # The provider appears only through the evidence() call, not as a listing.
    assert "SportsCardsPro" not in group_fn
