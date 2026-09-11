from pathlib import Path


def test_compare_controls_do_not_offer_sportscardspro_as_store():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    controls_start = html.index('<div class="controls">')
    controls_end = html.index('</div>', controls_start)
    assert "SportsCardsPro" not in html[controls_start:controls_end]
