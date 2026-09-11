from pathlib import Path


def test_research_panel_does_not_enlarge_card_photos():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert ".card{width:190px" in html
    assert ".card-image{width:100%;height:120px" in html
    assert "object-fit:contain" in html
