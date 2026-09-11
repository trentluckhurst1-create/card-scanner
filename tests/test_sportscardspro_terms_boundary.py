from pathlib import Path


def test_public_compare_has_no_sportscardspro_api_or_embedded_price_payload():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8").lower()
    assert "sportscardspro.com/api/" not in html
    assert "sportscardspro_price" not in html
    assert "sportscardspro_sales" not in html
    assert "sportscardspro_recent_sales" not in html


def test_contract_requires_permission_before_public_price_integration():
    text = Path("docs/SPORTSCARDSPRO_EVIDENCE_CONTRACT.md").read_text(encoding="utf-8")
    assert "does not scrape, cache, persist, export, or republish" in text
    assert "without express permission" in text
