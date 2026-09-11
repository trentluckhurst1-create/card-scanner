from pathlib import Path


def test_active_card_count_comes_from_exact_feed_market_cards():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "$('cards').textContent=(payload.market_cards||[]).length" in html
