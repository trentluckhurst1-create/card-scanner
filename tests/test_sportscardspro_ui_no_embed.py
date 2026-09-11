from pathlib import Path


def test_compare_uses_external_anchor_not_embed():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "sportscardsProLink(g)" in html
    assert "<iframe" not in html
