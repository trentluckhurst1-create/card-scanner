from pathlib import Path


def test_mobile_card_photos_remain_compact():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert ".card{width:150px}.card-image{height:100px}" in html
