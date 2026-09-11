from pathlib import Path


def test_live_compare_keeps_text_below_uniform_card_images():
    html = (Path(__file__).resolve().parents[1] / "docs" / "live-compare.html").read_text(encoding="utf-8")
    assert ".card{width:190px" in html
    assert ".card-image{width:100%;height:255px" in html
    assert "object-fit:contain" in html
    assert ".body{padding:10px 11px 11px;background:#0c1928" in html
    assert '<div class="card-image">' in html
    assert '</div><div class="body">' in html
    assert "position:absolute" not in html
    assert "listingIdentity(l)" in html
    assert "only the individual serial copy number may differ" in html
