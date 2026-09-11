from pathlib import Path


def test_guard_keeps_buy_behind_governed_sold_evidence():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "cannot create BUY or STRONG BUY without genuine governed sold evidence" in html
