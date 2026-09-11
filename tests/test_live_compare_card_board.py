from pathlib import Path


def test_live_compare_renders_actual_listing_cards_from_market_feed():
    root = Path(__file__).resolve().parents[1]
    html = (root / "docs" / "live-compare.html").read_text(encoding="utf-8")

    assert "Compare actual cards across stores" in html
    assert "payload.market_cards" in html
    assert "cardIndex=new Map" in html
    assert "card-image" in html
    assert "Open listing at" in html
    assert "l.title" in html
    assert "l.landed_aud??l.asking_price" in html
    assert "EXACT SAME CARD" in html
    assert "SAME PRODUCT · DIFFERENT VARIANT" in html
    assert "PLAYER / YEAR CONTEXT" in html
    assert "Browse all cards" in html
    assert "Active asks are comparison evidence only" in html
    assert "fair value" in html.lower()
    assert "BUY or STRONG BUY" in html
