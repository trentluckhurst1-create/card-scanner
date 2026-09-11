from pathlib import Path


def test_all_card_tiles_use_single_fixed_card_class():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert 'class="card ${best?' in html
    assert ".card{width:190px" in html
