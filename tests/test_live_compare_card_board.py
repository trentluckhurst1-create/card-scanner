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
    assert "Browse all cards" in html
    assert "Active asks are comparison evidence only" in html
    assert "fair value" in html.lower()
    assert "BUY or STRONG BUY" in html


def test_live_compare_is_exact_card_only_and_uses_compact_equal_images():
    root = Path(__file__).resolve().parents[1]
    html = (root / "docs" / "live-compare.html").read_text(encoding="utf-8")

    assert "g.comparison_type==='EXACT_CARD'" in html
    assert "filter(g=>g.comparison_type==='EXACT_CARD'" in html
    assert "Different variants are deliberately not compared" in html
    assert ".card{width:190px" in html
    assert ".card-image{width:100%;height:120px" in html
    assert ".card-image img{width:100%;height:100%;object-fit:contain}" in html
    assert "All comparison types" not in html
    assert "Same product / different variants</option>" not in html
    assert "Player/year context</option>" not in html
