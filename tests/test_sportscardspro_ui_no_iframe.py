from pathlib import Path


def test_compare_does_not_embed_sportscardspro_in_iframe():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8").lower()
    assert "<iframe" not in html
