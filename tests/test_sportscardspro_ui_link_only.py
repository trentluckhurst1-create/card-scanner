from pathlib import Path


def test_sportscardspro_evidence_is_external_link_not_price_table():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "Check SportsCardsPro ↗" in html
    assert "SportsCardsPro sales table" not in html
