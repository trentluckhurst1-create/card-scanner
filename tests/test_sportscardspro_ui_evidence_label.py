from pathlib import Path


def test_evidence_panel_is_labeled_recent_sales_research():
    html = Path("docs/live-compare.html").read_text(encoding="utf-8")
    assert "<strong>Recent-sales research</strong>" in html
