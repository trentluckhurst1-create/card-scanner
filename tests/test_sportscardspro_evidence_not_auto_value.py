from pathlib import Path


def test_public_copy_does_not_call_sportscardspro_a_fair_value():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8").lower()
    assert "sportscardspro fair value" not in html
