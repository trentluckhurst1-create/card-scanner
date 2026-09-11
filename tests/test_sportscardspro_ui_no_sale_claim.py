from pathlib import Path


def test_ui_does_not_claim_specific_recent_sale_amount():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "Last sold:" not in html
    assert "Recent sale: $" not in html
