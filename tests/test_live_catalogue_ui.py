from pathlib import Path


def test_live_catalogue_uses_full_automated_market_feed():
    root = Path(__file__).resolve().parents[1]
    html = (root / "docs" / "catalogue.html").read_text(encoding="utf-8")
    route = (root / "docs" / "catalogue" / "index.html").read_text(encoding="utf-8")

    assert "active_market.json" in html
    assert "market_cards" in html
    assert "Full live active-card catalogue" in html
    assert "location.replace('../catalogue.html')" in route


def test_live_catalogue_has_search_filter_sort_and_pagination_controls():
    html = (Path(__file__).resolve().parents[1] / "docs" / "catalogue.html").read_text(encoding="utf-8")

    assert 'id="q"' in html
    assert 'id="sport"' in html
    assert 'id="store"' in html
    assert 'id="sort"' in html
    assert 'id="pageSize"' in html
    assert "48 per page" in html
    assert 'id="pager"' in html
    assert "Price low → high" in html
    assert "Price high → low" in html


def test_live_catalogue_surfaces_identity_images_and_direct_store_links():
    html = (Path(__file__).resolve().parents[1] / "docs" / "catalogue.html").read_text(encoding="utf-8")

    assert "image_url" in html
    assert "card_number" in html
    assert "parallel" in html
    assert "serial_total" in html
    assert "grader" in html
    assert "Open at store" in html
    assert 'target="_blank"' in html


def test_live_catalogue_preserves_active_ask_governance():
    html = (Path(__file__).resolve().parents[1] / "docs" / "catalogue.html").read_text(encoding="utf-8")

    assert "active asking prices only" in html.lower()
    assert "does not mean it has been sold-comp researched" in html.lower()
    assert "not fair value" in html.lower()
    assert "BUY/STRONG_BUY" in html
