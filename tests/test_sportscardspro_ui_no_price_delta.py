from pathlib import Path


def test_sportscardspro_is_not_used_in_price_delta_calculation():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    start = html.index("function matrix(listings)")
    end = html.index("function card(", start)
    assert "sportscards" not in html[start:end].lower()
